import os, time, threading, numpy as np, serial, RPi.GPIO as GPIO, spidev, adafruit_fingerprint
from RPLCD.gpio import CharLCD
from scipy.signal import butter, filtfilt, find_peaks
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from datetime import datetime
from firebase_client import push_pulse, push_fingerprint, push_ecg_batch, delete_fingerprint_from_db

# ===== Hardware Setup =====
GPIO.setmode(GPIO.BCM)
lcd = CharLCD(numbering_mode=GPIO.BCM, cols=16, rows=2,
              pin_rs=25, pin_e=24, pins_data=[23,17,18,22], pin_backlight=2)
uart = serial.Serial("/dev/ttyS0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)
spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 1350000

def read_adc(channel=0):
    adc = spi.xfer2([1,(8+channel)<<4,0])
    return ((adc[1]&3)<<8) + adc[2]

# ================== ECG ==================
class ECGProcessor:
    def __init__(self, fs=100):
        self.fs = fs
        self.b, self.a = butter(4,[0.5/(fs/2),40/(fs/2)],btype='bandpass')
        self.b_high, self.a_high = butter(4,0.5/(fs/2),btype='highpass')
        self.buffer = np.zeros(5*fs)
        self.filtered = np.zeros(5*fs)
    def process(self, sample):
        self.buffer = np.roll(self.buffer,-1)
        self.buffer[-1] = sample
        filtered = filtfilt(self.b,self.a,self.buffer)
        filtered = filtfilt(self.b_high,self.a_high,filtered)
        self.filtered = np.roll(self.filtered,-1)
        self.filtered[-1] = filtered[-1]
        return self.filtered[-1]

class ECGDisplay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ECG Monitor")
        self.fig = Figure(figsize=(14,6), dpi=80)
        self.ax = self.fig.add_subplot(111)
        self.ax.grid(True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.ecg_line, = self.ax.plot([],[])
        self.fs = 100
        self.duration = 8
        self.samples = self.fs*self.duration
        self.time_axis = np.linspace(0,self.duration,self.samples)
        self.filtered_data = np.zeros(self.samples)
        self.processor = ECGProcessor(self.fs)
        self.running = True
    def update(self):
        if not self.running: return
        raw = read_adc()
        filtered = self.processor.process(raw)
        self.filtered_data = np.roll(self.filtered_data,-1)
        self.filtered_data[-1] = filtered
        self.ecg_line.set_data(self.time_axis,self.filtered_data)
        self.ax.set_xlim(self.time_axis[-1]-5,self.time_axis[-1])
        self.ax.relim(); self.ax.autoscale_view()
        self.canvas.draw()
        self.root.after(10,self.update)
    def save_ecg_image(self):
        folder = "ecg_images"
        os.makedirs(folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(folder,f"ECG_{timestamp}.jpg")
        plt.figure(figsize=(10,3))
        plt.plot(self.filtered_data[-3000:], linewidth=1)
        plt.title("ECG Signal (Last 30s)"); plt.xlabel("Samples"); plt.ylabel("Amplitude"); plt.grid(True)
        plt.tight_layout(); plt.savefig(filename,dpi=150); plt.close()
        print(f"[INFO] ECG image saved locally: {filename}")
        return filename
    def close(self, user_email=None):
        self.running=False
        self.save_ecg_image()
        try: push_ecg_batch(self.filtered_data[-3000:], fs=self.fs, user_email=user_email)
        except: pass
        self.root.destroy()

def run_ecg_monitor(user_email=None):
    def start_gui():
        root = ECGDisplay()
        root.root.protocol("WM_DELETE_WINDOW", lambda: root.close(user_email))
        root.update()
        root.root.after(30000, lambda: root.close(user_email))
        root.root.mainloop()
    threading.Thread(target=start_gui).start()
    return "ECG monitoring started."

# ================== Fingerprint ==================
def enroll_fingerprint(user_email=None):
    lcd.clear(); lcd.write_string("Enroll: 1st scan")
    try:
        id_num=1
        while finger.get_image()!=adafruit_fingerprint.OK: pass
        finger.image_2_tz(1); lcd.clear(); lcd.write_string("Remove finger"); time.sleep(2)
        lcd.clear(); lcd.write_string("2nd scan now")
        while finger.get_image()!=adafruit_fingerprint.OK: pass
        finger.image_2_tz(2)
        if finger.compare_templates()!=adafruit_fingerprint.OK:
            lcd.clear(); lcd.write_string("No match!"); push_fingerprint("enroll",id_num,False,user_email)
            return "Fingerprint scans do not match."
        if finger.create_model()==adafruit_fingerprint.OK:
            if finger.store_model(id_num)==adafruit_fingerprint.OK:
                push_fingerprint("enroll",id_num,True,user_email)
                lcd.clear(); lcd.write_string("Enroll success")
                return f"Fingerprint ID {id_num} enrolled successfully."
            else: lcd.clear(); lcd.write_string("Store failed"); return "Error: failed to store fingerprint."
        else: lcd.clear(); lcd.write_string("Model fail"); return "Error: failed to create model."
    except Exception as e:
        lcd.clear(); lcd.write_string("Enroll error"); push_fingerprint("enroll",0,False,user_email)
        return f"Enrollment error: {e}"

def verify_and_monitor(user_email=None):
    lcd.clear(); lcd.write_string("Verifying...")
    try:
        while finger.get_image()!=adafruit_fingerprint.OK: pass
        finger.image_2_tz(1)
        if finger.finger_search()==adafruit_fingerprint.OK:
            lcd.clear(); lcd.write_string("Matched!")
            run_ecg_monitor(user_email)
            return "Verified! ECG started."
        else: lcd.write_string("No match"); return "Fingerprint not recognized."
    except Exception as e:
        return f"Error verifying: {e}"

def delete_fingerprint(user_email=None):
    try:
        finger.delete_model(1)
        if user_email: delete_fingerprint_from_db(user_email)
        return "Deleted fingerprint ID 1 and removed user data from Firebase."
    except Exception as e:
        return f"Delete error: {e}"

# ================== Pulse ==================
def pulse_check(user_email=None):
    try:
        lcd.clear(); lcd.write_string("Pulse measuring")
        SAMPLE_RATE=100; DURATION=10; PULSE_CHANNEL=0
        raw_signal=[]; start_time=time.time()
        while time.time()-start_time<DURATION:
            raw_signal.append(read_adc(PULSE_CHANNEL)); time.sleep(1/SAMPLE_RATE)
        raw_signal=np.array(raw_signal); signal=raw_signal-np.mean(raw_signal)
        signal=signal/np.max(np.abs(signal))
        nyquist=0.5*SAMPLE_RATE; low, high=0.7/nyquist, 3.0/nyquist
        b,a=butter(4,[low,high],btype='band'); filtered=filtfilt(b,a,signal)
        min_peak=np.mean(filtered)+0.5*np.std(filtered)
        peaks,_=find_peaks(filtered,height=min_peak,distance=SAMPLE_RATE*0.4)
        bpm=60/np.mean(np.diff(peaks)/SAMPLE_RATE)
        push_pulse(bpm,"Normal",user_email)
        lcd.clear(); lcd.write_string(f"Pulse {bpm:.0f}")
        return f"Pulse rate: {bpm:.1f} BPM"
    except Exception as e:
        return f"Pulse check error: {e}"
