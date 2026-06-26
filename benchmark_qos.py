import urllib.request
import subprocess
import threading
import time
import statistics
import re
import os

# --- KONFIGURASI BENCHMARK ---
# File dummy 10MB untuk tes download
DOWNLOAD_URL = "http://speedtest.tele2.net/10MB.zip"
# Server tujuan ping (simulasi server game)
GAME_SERVER = "8.8.8.8"
PING_COUNT = 15 # Berapa kali ping dilakukan di setiap tahap
# ------------------------------

is_downloading = False

def ping_server(server, count):
    """Melakukan ping dan mengembalikan daftar waktu balasan (ms)"""
    latencies = []
    print(f"[*] Melakukan ping ke {server} sebanyak {count} kali...")
    
    # Gunakan ping bawaan OS
    cmd = ["ping", "-n" if os.name == "nt" else "-c", str(count), server]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    for line in process.stdout:
        # Regex menangkap "time=XXms" atau "waktu=XXms"
        match = re.search(r'(?:time|waktu)[=<]([\d\.]+)ms', line, re.IGNORECASE)
        if match:
            latencies.append(float(match.group(1)))
            print(f"    Ping reply: {match.group(1)} ms")
            
    return latencies

def download_worker():
    """Mengunduh file besar di background untuk membuat kemacetan (bufferbloat)"""
    global is_downloading
    is_downloading = True
    print(f"\n[>>>] MEMULAI DOWNLOAD BERAT ({DOWNLOAD_URL}) [>>>]")
    try:
        urllib.request.urlretrieve(DOWNLOAD_URL, "dummy_download.bin")
        print("[<<<] DOWNLOAD SELESAI [<<<]")
    except Exception as e:
        print(f"[!] Gagal download: {e}")
    finally:
        is_downloading = False
        if os.path.exists("dummy_download.bin"):
            os.remove("dummy_download.bin")

def print_stats(name, latencies):
    if not latencies:
        print(f"[-] Gagal mendapatkan latensi untuk: {name}")
        return 0
    avg = statistics.mean(latencies)
    maks = max(latencies)
    print(f"\n=== HASIL {name} ===")
    print(f"    Rata-rata Latency: {avg:.2f} ms")
    print(f"    Spike Tertinggi  : {maks:.2f} ms")
    print(f"    Packet Loss      : {(PING_COUNT - len(latencies)) / PING_COUNT * 100:.0f}%")
    return avg

if __name__ == "__main__":
    print("=====================================================")
    print("   QoS CAKE ADAPTIVE - BENCHMARK & BUFFERBLOAT TEST  ")
    print("=====================================================\n")
    
    print("Tahap 1: Mengukur Latensi Game (Tanpa Beban / Idle)")
    idle_latencies = ping_server(GAME_SERVER, PING_COUNT)
    
    print("\nTahap 2: Menyalakan Beban Download (Memancing Bufferbloat)")
    dl_thread = threading.Thread(target=download_worker)
    dl_thread.start()
    
    # Tunggu sebentar agar download mencapai kecepatan puncak
    time.sleep(3)
    
    print("\nTahap 3: Mengukur Latensi Game (Saat Jaringan Sibuk)")
    load_latencies = []
    if is_downloading:
        load_latencies = ping_server(GAME_SERVER, PING_COUNT)
    
    print("\nMenunggu sisa download selesai...")
    dl_thread.join()
    
    print("\n=====================================================")
    print("                   KESIMPULAN AKHIR                  ")
    print("=====================================================")
    idle_avg = print_stats("KONDISI NORMAL (IDLE)", idle_latencies)
    load_avg = print_stats("KONDISI SIBUK (DOWNLOAD + GAME)", load_latencies)
    
    if idle_avg > 0 and load_avg > 0:
        selisih = load_avg - idle_avg
        print(f"\n[!] Kenaikan Latency Akibat Beban: +{selisih:.2f} ms")
        if selisih < 20:
            print("[+] KESIMPULAN: LULUS! QoS CAKE bekerja sempurna meredam Bufferbloat.")
            print("    Koneksi game tetap stabil meskipun ada download berat.")
        else:
            print("[-] KESIMPULAN: ADA BUFFERBLOAT. QoS CAKE mungkin perlu disetel ulang limit bandwidth-nya.")
