from flask import Flask, render_template, request, jsonify
import threading
import time
import subprocess
import os
import signal
import sys
from collections import deque
import datetime
from bee_health_db import BeeHealthDatabase

app = Flask(__name__)

# Configuration
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DETECTION_INPUT = os.environ.get("BEE_INPUT", "rpi")
DETECTION_COMMAND = [
    sys.executable, "-u", os.path.join(PROJECT_DIR, "detection.py"),
    "--input", DETECTION_INPUT,
    "--hef-path", os.environ.get("BEE_HEF", os.path.join(PROJECT_DIR, "first_15k.hef")),
    "--labels-json", os.path.join(PROJECT_DIR, "labels.json"),
]
DEBUG = os.environ.get("BEE_DEBUG", "0") == "1"
MAX_DATA_POINTS = 100  # For time-series data

# Initialize database connection
db = BeeHealthDatabase(os.environ.get("BEE_DB_PATH", os.path.join(PROJECT_DIR, "bee_health.db")))

# Global variables
detection_active = False
detection_thread = None
detection_process = None
process_lock = threading.RLock()
lifecycle_lock = threading.Lock()
last_detection_error = None

# Time series data for charting
time_series_data = {
    "timestamps": deque(maxlen=MAX_DATA_POINTS),
    "bee_counts": deque(maxlen=MAX_DATA_POINTS),
    "varroa_counts": deque(maxlen=MAX_DATA_POINTS),
    "infestation_ratio": deque(maxlen=MAX_DATA_POINTS),
}

# Current statistics
detection_stats = {
    "total_frames": 0,
    "total_bees": 0,
    "total_varroa": 0,
    "unique_bees": 0,
    "unique_varroa": 0,
    "current_bees": 0,
    "current_varroa": 0,
    "fps": 0,
    "infestation_ratio": 0,
    "infestation_risk_level": "Unknown",
    "last_update": time.time()
}

# Risk level thresholds (varroa:bee ratio)
RISK_THRESHOLDS = {
    "low": 0.05,       # <5% - healthy colony
    "moderate": 0.10,  # 5-10% - monitor closely
    "high": 0.15,      # 10-15% - intervention recommended
    "critical": 0.20   # >15% - immediate action required
}

def update_time_series():
    """Update time series data for charts and save to database"""
    global time_series_data, detection_stats
    
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    time_series_data["timestamps"].append(current_time)
    time_series_data["bee_counts"].append(detection_stats["current_bees"])
    time_series_data["varroa_counts"].append(detection_stats["current_varroa"])
    
    # Calculate infestation ratio based on unique objects (avoid division by zero)
    if detection_stats["unique_bees"] > 0:
        ratio = detection_stats["unique_varroa"] / detection_stats["unique_bees"]
    else:
        ratio = 0
    
    # Store ratio in time series and detection stats
    time_series_data["infestation_ratio"].append(ratio)
    detection_stats["infestation_ratio"] = ratio
    
    # Update Colony Health Status based on unique object ratio
    if detection_stats["unique_bees"] == 0:
        detection_stats["infestation_risk_level"] = "Unknown"
    elif ratio < RISK_THRESHOLDS["low"]:
        detection_stats["infestation_risk_level"] = "Low"
    elif ratio < RISK_THRESHOLDS["moderate"]:
        detection_stats["infestation_risk_level"] = "Moderate"
    elif ratio < RISK_THRESHOLDS["high"]:
        detection_stats["infestation_risk_level"] = "High"
    else:
        detection_stats["infestation_risk_level"] = "Critical"
    
    # Save metrics to database (every 100 frames to avoid excessive database writes)
    if detection_stats["total_frames"] % 100 == 0:
        db.save_metrics(
            unique_bee_count=detection_stats["unique_bees"],
            unique_varroa_count=detection_stats["unique_varroa"],
            frame_count=detection_stats["total_frames"],
            fps=detection_stats["fps"]
        )

def parse_detection_output(line):
    """Parse detection output lines for bee and varroa counts"""
    global detection_stats
    
    if DEBUG:
        print(f"Parsing line: {line}")
    
    # Parse unique bee and varroa counts for Cumulative Statistics, 
    # Infestation Ratio, and Colony Health Status
    if "Unique bees:" in line:
        try:
            unique_bee_count = int(line.split("Unique bees:")[1].strip())
            detection_stats["unique_bees"] = unique_bee_count
            
            # Use unique bees for Total Bees in Cumulative Statistics
            detection_stats["total_bees"] = unique_bee_count
            
        except (ValueError, IndexError) as e:
            if DEBUG:
                print(f"Error parsing unique bee count: {e}")
    
    if "Unique varroa:" in line:
        try:
            unique_varroa_count = int(line.split("Unique varroa:")[1].strip())
            detection_stats["unique_varroa"] = unique_varroa_count
            
            # Use unique varroa for Total Varroa in Cumulative Statistics
            detection_stats["total_varroa"] = unique_varroa_count
            
        except (ValueError, IndexError) as e:
            if DEBUG:
                print(f"Error parsing unique varroa count: {e}")
    
    # Parse current frame bee and varroa counts for Real-time Detection Trends
    # and Key Detection Metrics
    if "Current frame bees:" in line:
        try:
            current_bee_count = int(line.split("Current frame bees:")[1].strip())
            detection_stats["current_bees"] = current_bee_count
        except (ValueError, IndexError) as e:
            if DEBUG:
                print(f"Error parsing current frame bee count: {e}")
    
    if "Current frame varroa:" in line:
        try:
            current_varroa_count = int(line.split("Current frame varroa:")[1].strip())
            detection_stats["current_varroa"] = current_varroa_count
        except (ValueError, IndexError) as e:
            if DEBUG:
                print(f"Error parsing current frame varroa count: {e}")
    
    # Use individual detections to update current bee/varroa counts
    if "Label: bee" in line:
        # Optional: Process individual bee detections if needed
        pass
    
    if "Label: varroa" in line:
        # Optional: Process individual varroa detections if needed
        pass
    
    # Frame count
    if "Frame count:" in line:
        try:
            frame_count = int(line.split("Frame count:")[1].strip())
            detection_stats["total_frames"] = frame_count
            
            # Calculate FPS
            current_time = time.time()
            time_diff = current_time - detection_stats["last_update"]
            if time_diff > 0:
                frame_diff = frame_count - detection_stats.get("last_frame", 0)
                if frame_diff > 0 and time_diff > 0.5:  # Update FPS every half second
                    detection_stats["fps"] = frame_diff / time_diff
                    detection_stats["last_frame"] = frame_count
                    detection_stats["last_update"] = current_time
            
            # Update time series data every 10 frames
            if frame_count % 10 == 0:
                update_time_series()
                
        except (ValueError, IndexError) as e:
            if DEBUG:
                print(f"Error parsing frame count: {e}")

def terminate_detection():
    """Stop only our child process group, allowing GStreamer to release the camera."""
    global detection_process
    with process_lock:
        process = detection_process
        if process is None:
            return
        for sig, timeout in ((signal.SIGINT, 3), (signal.SIGTERM, 2), (signal.SIGKILL, 2)):
            if process.poll() is not None:
                break
            try:
                os.killpg(process.pid, sig)
                process.wait(timeout=timeout)
                break
            except ProcessLookupError:
                break
            except subprocess.TimeoutExpired:
                continue
        detection_process = None

def detection_loop():
    """Thread function for the detection process"""
    global detection_active, detection_stats, detection_process, last_detection_error
    
    try:
        # Reset statistics
        detection_stats["total_frames"] = 0
        detection_stats["total_bees"] = 0
        detection_stats["total_varroa"] = 0
        detection_stats["unique_bees"] = 0
        detection_stats["unique_varroa"] = 0
        detection_stats["current_bees"] = 0
        detection_stats["current_varroa"] = 0
        detection_stats["fps"] = 0
        detection_stats["infestation_ratio"] = 0
        detection_stats["infestation_risk_level"] = "Unknown"
        detection_stats["last_update"] = time.time()
        detection_stats["last_frame"] = 0
        
        # Start a new database session
        source_file = DETECTION_INPUT
        db.start_new_session(source=source_file, notes="Automatic detection")
        
        # Clear time series data
        time_series_data["timestamps"].clear()
        time_series_data["bee_counts"].clear()
        time_series_data["varroa_counts"].clear()
        time_series_data["infestation_ratio"].clear()
        
        env = os.environ.copy()
        
        # Launch the detection command as a subprocess
        if DEBUG:
            print(f"Starting detection process with command: {DETECTION_COMMAND}")
        
        # Own a process group so stopping detection never kills other camera/apps.
        with process_lock:
            if not detection_active:
                return
            detection_process = subprocess.Popen(
                DETECTION_COMMAND,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Drain errors too; avoid a full stderr pipe.
                text=True,
                bufsize=1,
                env=env,
                cwd=PROJECT_DIR,
                start_new_session=True,
            )
            process = detection_process

        print(f"Started detection process with PID: {process.pid}")

        # Process stdout in real-time
        recent_output = deque(maxlen=12)
        while detection_active:
            line = process.stdout.readline()
            if not line:
                break
                
            line = line.strip()
            if line:
                recent_output.append(line)
                if DEBUG:
                    print(f"Detection output: {line}")
                parse_detection_output(line)
        if detection_active:
            code = process.wait()
            last_detection_error = f"Detection exited ({code}): " + "\n".join(recent_output)
            print(last_detection_error)

    except Exception as e:
        last_detection_error = str(e)
        print(f"Error in detection loop: {e}")
    finally:
        try:
            terminate_detection()
            db.end_session()
        finally:
            detection_active = False
            print("Detection thread exiting")

def signal_handler(sig, frame):
    """Handle termination signals"""
    print(f"Received signal {sig}, cleaning up and exiting...")
    global detection_active
    detection_active = False
    terminate_detection()
    if detection_thread:
        detection_thread.join(timeout=5)
    sys.exit(0)

@app.route('/')
def index():
    """Render the dashboard page"""
    return render_template('index.html')

@app.route('/start_detection', methods=['POST'])
def start_detection():
    """Start the detection process"""
    global detection_active, detection_thread, last_detection_error
    with lifecycle_lock:
        if detection_active:
            return jsonify({"status": "already_running"})
        if detection_thread and detection_thread.is_alive():
            return jsonify({"status": "error", "message": "Previous session is still stopping"}), 409
        last_detection_error = None
        detection_active = True
        detection_thread = threading.Thread(target=detection_loop, daemon=True)
        detection_thread.start()
        # Catch immediate startup failures instead of silently claiming success.
        time.sleep(1)
        if not detection_active:
            return jsonify({"status": "error", "message": last_detection_error}), 500
        return jsonify({"status": "started"})

@app.route('/stop_detection', methods=['POST'])
def stop_detection():
    """Stop the detection process"""
    global detection_active
    
    with lifecycle_lock:
        if not detection_active and not (detection_thread and detection_thread.is_alive()):
            return jsonify({"status": "already_stopped"})
        detection_active = False
        terminate_detection()
        if detection_thread:
            detection_thread.join(timeout=5.0)
            if detection_thread.is_alive():
                return jsonify({"status": "error", "message": "Session is still stopping"}), 503
        return jsonify({"status": "stopped"})

@app.route('/get_stats')
def get_stats():
    """Return the current detection statistics"""
    if DEBUG:
        print(f"Sending stats to client: {detection_stats}")
    return jsonify({**detection_stats, "active": detection_active, "error": last_detection_error})

@app.route('/get_time_series')
def get_time_series():
    """Return time series data for charts"""
    result = {
        "timestamps": list(time_series_data["timestamps"]),
        "bee_counts": list(time_series_data["bee_counts"]),
        "varroa_counts": list(time_series_data["varroa_counts"]),
        "infestation_ratio": list(time_series_data["infestation_ratio"]),
    }
    return jsonify(result)

# Database access routes
@app.route('/api/sessions')
def get_sessions():
    """Get list of recording sessions"""
    limit = request.args.get('limit', 10, type=int)
    sessions = db.get_sessions(limit=limit)
    return jsonify(sessions)

@app.route('/api/metrics')
def get_metrics():
    """Get stored metrics"""
    limit = request.args.get('limit', 100, type=int)
    session_id = request.args.get('session_id', None, type=int)
    metrics = db.get_latest_metrics(limit=limit, session_id=session_id)
    return jsonify(metrics)

# Email testing endpoint - kept for functionality
@app.route('/test-email')
def test_email():
    """Test email functionality with timeout and better error handling"""
    result = {
        "status": "unknown",
        "message": "",
        "error_details": ""
    }
    
    try:
        # Get the most recent session
        sessions = db.get_sessions(limit=1)
        if not sessions:
            result["status"] = "error"
            result["message"] = "No sessions found to send test email."
            return jsonify(result)
            
        session_id = sessions[0]['session_id']
        
        # Check if email credentials exist
        email_service = db.email_service
        if not email_service.username or not email_service.password:
            result["status"] = "error"
            result["message"] = "Missing email credentials. Check BEE_MONITOR_EMAIL and BEE_MONITOR_EMAIL_PASSWORD environment variables."
            result["error_details"] = f"Username available: {'Yes' if email_service.username else 'No'}, Password available: {'Yes' if email_service.password else 'No'}"
            return jsonify(result)
        
        # Check recipient
        if not email_service.recipient:
            result["status"] = "error"
            result["message"] = "No recipient email address configured."
            return jsonify(result)
        
        # Add a timeout for the email sending
        import threading
        import queue

        # Use a queue to get the result from the thread
        q = queue.Queue()
        
        def send_email_with_timeout():
            try:
                success = email_service.send_session_summary(session_id, db.db_path)
                q.put(("success" if success else "error", 
                      f"Email {'sent successfully' if success else 'failed to send'} for session {session_id}"))
            except Exception as e:
                q.put(("error", f"Exception while sending email: {str(e)}"))
        
        # Start email sending in a separate thread
        email_thread = threading.Thread(target=send_email_with_timeout)
        email_thread.daemon = True
        email_thread.start()
        
        # Wait for result with a timeout
        try:
            status, message = q.get(timeout=10)  # 10 second timeout
            result["status"] = status
            result["message"] = message
        except queue.Empty:
            result["status"] = "error"
            result["message"] = "Email sending timed out after 10 seconds. Check SMTP server settings."
        
        return jsonify(result)
        
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Error in test-email route"
        result["error_details"] = str(e)
        return jsonify(result)

if __name__ == '__main__':
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the Flask app
    # LAN-only development server; never expose this unauthenticated app publicly.
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
