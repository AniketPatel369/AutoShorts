"""
Auto Shorts — Module: Reframer

Implements active-speaker-aware vertical reframing.
Correlates mouth openness landmarks from MediaPipe Face Mesh with audio energy to detect who is speaking,
debounces speaker switches, and applies smooth exponential moving average (EMA) camera panning.
"""
import logging
import subprocess
import wave
import tempfile
import os
from pathlib import Path
import numpy as np
import cv2
import mediapipe as mp

logger = logging.getLogger(__name__)


def reframe_active_speaker(
    video_path: str,
    audio_path: str,
    aspect_ratio: str,
    out_path: str,
    debug: bool = False,
) -> str:
    """
    Returns path to vertically-cropped video tracking the active speaker.
    
    Args:
        video_path: Path to the input video file (e.g. mp4).
        audio_path: Path to the audio file, or empty string to extract from video.
        aspect_ratio: Target aspect ratio, e.g. "9:16".
        out_path: Path to write the reframed vertical video.
        debug: If True, renders bounding boxes and scoring metrics on the video.
    """
    logger.info(f"Starting active-speaker reframing for: {video_path}")
    
    # 1. Open Video Reader and get properties
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if fps <= 0 or total_frames <= 0:
        # Fallback defaults
        fps = 30.0
        total_frames = 900
        
    logger.info(f"Video specs: {width}x{height} @ {fps:.2f} fps, {total_frames} frames")
    
    # Target crop dimensions based on aspect ratio (e.g. "9:16")
    if aspect_ratio == "9:16":
        target_w = int(height * 9 / 16)
        target_h = height
    else:
        # Fallback to standard 9:16 center crop width
        target_w = int(height * 9 / 16)
        target_h = height
        
    # Ensure target_w is even for video encoders
    if target_w % 2 != 0:
        target_w += 1
        
    # Clamp crop width to video frame width
    if target_w > width:
        target_w = width
        
    # 2. Extract and Align Audio Energy (RMS)
    temp_wav = None
    if not audio_path or not Path(audio_path).exists():
        # Extract audio using ffmpeg to a temporary WAV file
        temp_wav_fd, temp_wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(temp_wav_fd)
        temp_wav = temp_wav_path
        
        logger.info("Extracting audio from video...")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            temp_wav
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        active_audio_path = temp_wav
    else:
        active_audio_path = audio_path
        
    audio_energy = _compute_audio_energy(active_audio_path, fps, total_frames)
    
    # Clean up temp wav if created
    if temp_wav and os.path.exists(temp_wav):
        try:
            os.remove(temp_wav)
        except OSError:
            pass
            
    # Dynamic speech threshold: 12% of max audio energy, min 0.01
    max_energy = np.max(audio_energy) if len(audio_energy) > 0 else 0.0
    speech_threshold = max(0.01, 0.12 * max_energy)
    logger.info(f"Speech detection threshold set to: {speech_threshold:.4f} (max energy: {max_energy:.4f})")
    
    # 3. Pass 1: Face Landmark Detection & Tracking
    logger.info("Pass 1: Detecting faces and tracking landmarks...")
    mp_face_mesh = mp.solutions.face_mesh
    
    # Store tracked face data per frame
    # frame_faces[frame_idx] = { face_id: { 'bbox': [xmin, ymin, xmax, ymax], 'center': (x, y), 'mouth_open': val } }
    frame_faces = [{} for _ in range(total_frames)]
    
    # Face tracker tracks: face_id -> {'last_box': [xmin, ymin, xmax, ymax], 'last_seen': frame_idx, 'mouth_history': []}
    tracks = {}
    next_track_id = 1
    
    # Max frames a track can be missing before being closed
    max_missing_frames = int(fps * 0.4) # ~400ms
    
    with mp_face_mesh.FaceMesh(
        max_num_faces=4,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:
        
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame_idx >= total_frames:
                break
                
            # Convert to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)
            
            detections = []
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Calculate bounding box in pixels
                    xs = [lm.x * width for lm in face_landmarks.landmark]
                    ys = [lm.y * height for lm in face_landmarks.landmark]
                    xmin, xmax = int(min(xs)), int(max(xs))
                    ymin, ymax = int(min(ys)), int(max(ys))
                    
                    # Clamp bounding boxes to image dimensions
                    xmin = max(0, xmin)
                    xmax = min(width, xmax)
                    ymin = max(0, ymin)
                    ymax = min(height, ymax)
                    
                    bbox = [xmin, ymin, xmax, ymax]
                    bbox_h = max(1, ymax - ymin)
                    
                    # Center of face coordinates
                    center_x = int((xmin + xmax) / 2)
                    center_y = int((ymin + ymax) / 2)
                    
                    # Inner lip landmarks: Upper inner lip (13), Lower inner lip (14)
                    upper_inner_y = face_landmarks.landmark[13].y * height
                    lower_inner_y = face_landmarks.landmark[14].y * height
                    
                    # Mouth openness: vertical distance normalized by face height
                    mouth_open = max(0.0, lower_inner_y - upper_inner_y) / bbox_h
                    
                    detections.append({
                        'bbox': bbox,
                        'center': (center_x, center_y),
                        'mouth_open': mouth_open
                    })
                    
            # Track Matching (IoU-based)
            # Find active tracks (seen recently)
            active_track_ids = [
                tid for tid, tdata in tracks.items()
                if frame_idx - tdata['last_seen'] <= max_missing_frames
            ]
            
            matched_detections = set()
            matched_tracks = set()
            
            # Compute IoU matrix between active tracks and detections
            matches = []
            for det_idx, det in enumerate(detections):
                for tid in active_track_ids:
                    iou = _compute_iou(det['bbox'], tracks[tid]['last_box'])
                    if iou > 0.3:
                        matches.append((iou, det_idx, tid))
                        
            # Sort matches by IoU descending
            matches.sort(key=lambda x: x[0], reverse=True)
            for iou, det_idx, tid in matches:
                if det_idx not in matched_detections and tid not in matched_tracks:
                    matched_detections.add(det_idx)
                    matched_tracks.add(tid)
                    
                    # Update track
                    tracks[tid]['last_box'] = detections[det_idx]['bbox']
                    tracks[tid]['last_seen'] = frame_idx
                    
                    # Save to frame data
                    frame_faces[frame_idx][tid] = {
                        'bbox': detections[det_idx]['bbox'],
                        'center': detections[det_idx]['center'],
                        'mouth_open': detections[det_idx]['mouth_open']
                    }
                    
            # Spawn new tracks for unmatched detections
            for det_idx, det in enumerate(detections):
                if det_idx not in matched_detections:
                    tid = next_track_id
                    next_track_id += 1
                    
                    tracks[tid] = {
                        'last_box': det['bbox'],
                        'last_seen': frame_idx
                    }
                    
                    frame_faces[frame_idx][tid] = {
                        'bbox': det['bbox'],
                        'center': det['center'],
                        'mouth_open': det['mouth_open']
                    }
                    
            frame_idx += 1
            
    cap.release()
    
    # 4. Fill history gaps for correlation analysis
    # Each face track needs a continuous mouth openness trace aligned frame-by-frame
    face_histories = {tid: np.zeros(total_frames) for tid in tracks.keys()}
    for f_idx in range(total_frames):
        for tid in tracks.keys():
            if tid in frame_faces[f_idx]:
                face_histories[tid][f_idx] = frame_faces[f_idx][tid]['mouth_open']
            else:
                face_histories[tid][f_idx] = 0.0  # mouth closed if not detected
                
    # Check total unique face tracks that were active for more than 5 frames
    meaningful_tracks = [
        tid for tid, history in face_histories.items()
        if np.sum(history > 0.0) >= 5
    ]
    
    logger.info(f"Tracked {len(tracks)} total tracks, {len(meaningful_tracks)} meaningful face tracks")
    
    # 5. Active Speaker Resolution & Smoothing Pass
    # Determine the target crop center for each frame
    target_centers = []
    
    # Default to frame center
    default_center = (int(width / 2), int(height / 2))
    
    # Parameters for correlation & debouncing
    window_size = int(fps * 0.8)  # ~800ms correlation window
    debounce_frames = int(fps * 0.45)  # ~450ms hold time before switching
    
    current_speaker = None
    candidate_speaker = None
    candidate_duration = 0
    
    # Track the active speaker ID per frame
    active_speaker_per_frame = []
    
    if len(meaningful_tracks) <= 1:
        # Fallback Step 7: Single speaker (or zero) detected
        logger.info("Single speaker detected. Applying single-speaker auto-tracking fallback.")
        single_tid = meaningful_tracks[0] if len(meaningful_tracks) == 1 else None
        
        for f_idx in range(total_frames):
            if single_tid and single_tid in frame_faces[f_idx]:
                target_centers.append(frame_faces[f_idx][single_tid]['center'])
                active_speaker_per_frame.append(single_tid)
            elif len(frame_faces[f_idx]) > 0:
                # Use whatever face is present
                first_tid = list(frame_faces[f_idx].keys())[0]
                target_centers.append(frame_faces[f_idx][first_tid]['center'])
                active_speaker_per_frame.append(first_tid)
            else:
                target_centers.append(default_center)
                active_speaker_per_frame.append(None)
    else:
        # Active Speaker Correlation Pipeline (2+ speakers)
        logger.info("Multiple speakers detected. Running active speaker audio-correlation analysis...")
        
        for f_idx in range(total_frames):
            is_speech = audio_energy[f_idx] > speech_threshold
            visible_tids = [tid for tid in meaningful_tracks if tid in frame_faces[f_idx]]
            
            if not is_speech or len(visible_tids) == 0:
                # Silence or no faces: hold current speaker
                active_speaker_per_frame.append(current_speaker)
            elif len(visible_tids) == 1:
                # Only one person visible: they are the default active speaker
                active_speaker_per_frame.append(visible_tids[0])
                current_speaker = visible_tids[0]
            else:
                # 2+ speakers visible: compute correlation over the sliding window
                start_w = max(0, f_idx - window_size)
                end_w = f_idx + 1
                
                audio_slice = audio_energy[start_w:end_w]
                
                best_score = -2.0
                best_tid = current_speaker or visible_tids[0]
                
                for tid in visible_tids:
                    mouth_slice = face_histories[tid][start_w:end_w]
                    score = _compute_pearson_correlation(mouth_slice, audio_slice)
                    
                    if score > best_score:
                        best_score = score
                        best_tid = tid
                        
                # Debounce Speaker Switching
                if current_speaker is None:
                    current_speaker = best_tid
                    active_speaker_per_frame.append(current_speaker)
                elif best_tid == current_speaker:
                    # Locked onto current speaker
                    candidate_speaker = None
                    candidate_duration = 0
                    active_speaker_per_frame.append(current_speaker)
                else:
                    # New speaker is winning correlation
                    if best_tid == candidate_speaker:
                        candidate_duration += 1
                    else:
                        candidate_speaker = best_tid
                        candidate_duration = 1
                        
                    if candidate_duration >= debounce_frames:
                        # Commit switch!
                        logger.info(f"Frame {f_idx}: Switching speaker target {current_speaker} -> {candidate_speaker}")
                        current_speaker = candidate_speaker
                        candidate_speaker = None
                        candidate_duration = 0
                        
                    active_speaker_per_frame.append(current_speaker)
                    
            # Convert active speaker to coordinates
            active_tid = active_speaker_per_frame[-1]
            if active_tid and active_tid in frame_faces[f_idx]:
                target_centers.append(frame_faces[f_idx][active_tid]['center'])
            elif len(frame_faces[f_idx]) > 0:
                # Fallback to the first face visible in frame
                first_tid = list(frame_faces[f_idx].keys())[0]
                target_centers.append(frame_faces[f_idx][first_tid]['center'])
            else:
                target_centers.append(default_center)
                
    # 6. Apply Exponential Moving Average (EMA) Smoothing
    smoothed_centers = []
    alpha = 0.12  # Smoothing factor (panning speed)
    
    current_smooth = None
    
    # Keep track of when we last saw any faces
    last_face_seen_idx = -9999
    
    for f_idx in range(total_frames):
        has_faces = len(frame_faces[f_idx]) > 0
        if has_faces:
            last_face_seen_idx = f_idx
            
        # Fallback to frame center if no face has been seen for > 1.0s (fps frames)
        if f_idx - last_face_seen_idx > int(fps):
            target = default_center
        else:
            target = target_centers[f_idx]
            
        if current_smooth is None:
            current_smooth = np.array(target, dtype=np.float32)
        else:
            current_smooth = current_smooth * (1.0 - alpha) + np.array(target, dtype=np.float32) * alpha
            
        smoothed_centers.append((int(current_smooth[0]), int(current_smooth[1])))
        
    # 7. Render Vertically Cropped Video (Pass 2)
    logger.info("Pass 2: Rendering cropped vertical video...")
    cap = cv2.VideoCapture(video_path)
    
    # Create temporary output file first to avoid conflicts, then mux audio
    temp_output_path = out_path + ".tmp.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_output_path, fourcc, fps, (target_w, target_h))
    
    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret or frame_idx >= total_frames:
            break
            
        center_x, center_y = smoothed_centers[frame_idx]
        
        # Calculate horizontal crop bounds
        crop_x1 = center_x - int(target_w / 2)
        crop_x2 = crop_x1 + target_w
        
        # Clamp bounds to video dimensions
        if crop_x1 < 0:
            crop_x1 = 0
            crop_x2 = target_w
        elif crop_x2 > width:
            crop_x2 = width
            crop_x1 = width - target_w
            
        # Crop vertical slice
        cropped = frame[0:height, crop_x1:crop_x2]
        
        # Resize to final dimensions if needed
        if cropped.shape[1] != target_w or cropped.shape[0] != target_h:
            cropped = cv2.resize(cropped, (target_w, target_h))
            
        # Render Debug Overlay if requested
        if debug:
            _draw_debug_overlay(
                cropped, frame, crop_x1, crop_x2, frame_idx, 
                frame_faces[frame_idx], active_speaker_per_frame[frame_idx], 
                audio_energy[frame_idx], speech_threshold, target_w, target_h
            )
            
        out.write(cropped)
        frame_idx += 1
        
    cap.release()
    out.release()
    
    # 8. Mux original audio into cropped video using FFmpeg
    logger.info("Muxing audio track back in...")
    try:
        if os.path.exists(out_path):
            os.remove(out_path)
            
        cmd = [
            "ffmpeg", "-y",
            "-i", temp_output_path,
            "-i", video_path, # pull audio from original clip
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            out_path
        ]
        # Run quietly
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # Clean up temp file
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
            
        logger.info(f"✅ Reframe complete: {out_path}")
        return out_path
    except Exception as e:
        logger.error(f"Failed to mux audio using ffmpeg: {e}")
        # If mux fails, fallback to using the un-muxed temp output path as result
        if os.path.exists(temp_output_path):
            if os.path.exists(out_path):
                os.remove(out_path)
            os.rename(temp_output_path, out_path)
        return out_path


def _compute_audio_energy(audio_path: str, fps: float, total_frames: int) -> np.ndarray:
    """Read mono WAV file and compute RMS energy per video frame timestamp."""
    try:
        with wave.open(audio_path, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            
            audio_bytes = wf.readframes(n_frames)
            
            if sampwidth == 2:
                samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 1:
                samples = np.frombuffer(audio_bytes, dtype=np.uint8).astype(np.float32) / 255.0
            else:
                # Unsupported sample depth, return zeros
                return np.zeros(total_frames)
                
            # Average channels if stereo
            if n_channels > 1:
                samples = samples.reshape(-1, n_channels).mean(axis=1)
                
            samples_per_frame = framerate / fps
            audio_energy = []
            
            for k in range(total_frames):
                start_sample = int(k * samples_per_frame)
                end_sample = int((k + 1) * samples_per_frame)
                segment = samples[start_sample:end_sample]
                if len(segment) > 0:
                    rms = np.sqrt(np.mean(segment ** 2))
                    audio_energy.append(rms)
                else:
                    audio_energy.append(0.0)
                    
            return np.array(audio_energy)
    except Exception as e:
        logger.error(f"Error computing audio energy: {e}")
        return np.zeros(total_frames)


def _compute_iou(box1: list[int], box2: list[int]) -> float:
    """Compute Intersection over Union between two bounding boxes."""
    x_min = max(box1[0], box2[0])
    y_min = max(box1[1], box2[1])
    x_max = min(box1[2], box2[2])
    y_max = min(box1[3], box2[3])
    
    if x_max <= x_min or y_max <= y_min:
        return 0.0
        
    intersection = (x_max - x_min) * (y_max - y_min)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    
    union = area1 + area2 - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union


def _compute_pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson correlation coefficient between two lists."""
    if len(x) < 5:
        return 0.0
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    x_std = np.std(x)
    y_std = np.std(y)
    if x_std < 1e-4 or y_std < 1e-4:
        return 0.0
    cov = np.mean((x - x_mean) * (y - y_mean))
    return cov / (x_std * y_std)


def _draw_debug_overlay(
    cropped: np.ndarray,
    original_frame: np.ndarray,
    crop_x1: int,
    crop_x2: int,
    frame_idx: int,
    faces: dict,
    active_speaker_id: int | None,
    current_energy: float,
    threshold: float,
    target_w: int,
    target_h: int
):
    """Draw face boxes, speaker status, and audio energy indicators on the output frame."""
    # Scale coordinates relative to the cropped vertical slice
    orig_h, orig_w = original_frame.shape[:2]
    
    # Overlay audio energy meter on top-left of cropped frame
    energy_percent = min(100, int((current_energy / (threshold * 3.0)) * 100)) if threshold > 0 else 0
    color = (0, 255, 0) if current_energy > threshold else (0, 0, 255)
    
    # Draw background box for stats
    cv2.rectangle(cropped, (10, 10), (320, 100), (0, 0, 0), -1)
    
    # Render audio energy text
    speech_status = "SPEECH" if current_energy > threshold else "SILENT"
    cv2.putText(
        cropped, f"RMS: {current_energy:.4f} ({speech_status})", 
        (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA
    )
    
    # Audio energy bar
    cv2.rectangle(cropped, (20, 50), (220, 60), (50, 50, 50), -1)
    cv2.rectangle(cropped, (20, 50), (20 + int(energy_percent * 2), 60), color, -1)
    
    # Draw face tracking overlays
    for tid, face in faces.items():
        bbox = face['bbox']
        
        # Check if the face is inside the cropped view
        xmin, ymin, xmax, ymax = bbox
        if xmax > crop_x1 and xmin < crop_x2:
            # Adjust x coordinates relative to the cropped frame
            c_xmin = xmin - crop_x1
            c_xmax = xmax - crop_x1
            
            is_active = (tid == active_speaker_id)
            box_color = (0, 255, 0) if is_active else (255, 255, 255)
            thickness = 2 if is_active else 1
            
            # Draw face box
            cv2.rectangle(cropped, (c_xmin, ymin), (c_xmax, ymax), box_color, thickness)
            
            # Draw face label
            label = f"ID: {tid} | Mouth: {face['mouth_open']:.3f}"
            if is_active:
                label += " [TALKING]"
            cv2.putText(
                cropped, label, (c_xmin, max(20, ymin - 10)), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, box_color, 1, cv2.LINE_AA
            )
