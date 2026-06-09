import time
import os
import csv
import shutil
import psutil
import threading
import matplotlib.pyplot as plt
from pathlib import Path
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

SELENIUM_MAJOR = int(selenium.__version__.split(".")[0])

# Configurações globais do experimento
sampling_interval = 1.0  
monitoring_active = False
current_tabs = 0 
TEST_DURATION_SEC = 180  # 3 minutos por execução
TOTAL_EXECUCOES = 30

def build_chrome_driver(driver_path, options):
    if SELENIUM_MAJOR >= 4: return webdriver.Chrome(service=ChromeService(driver_path), options=options)
    return webdriver.Chrome(executable_path=driver_path, options=options)

def build_firefox_driver(driver_path, options):
    if SELENIUM_MAJOR >= 4: return webdriver.Firefox(service=FirefoxService(driver_path), options=options)
    return webdriver.Firefox(executable_path=driver_path, options=options)

def resolve_driver_path(browser_name):
    base_dir = Path(__file__).resolve().parent
    driver_by_browser = {"chrome": "chromedriver", "firefox": "geckodriver"}
    local_project_driver = {
        "chrome": base_dir / "tools" / "chromedriver" / "chromedriver",
        "firefox": base_dir / "tools" / "geckodriver" / "geckodriver",
    }
    browser = browser_name.lower()
    candidate = local_project_driver[browser]
    
    if candidate.exists() and candidate.is_file():
        return str(candidate)

    local_driver = shutil.which(driver_by_browser[browser])
    if local_driver:
        return local_driver

    try:
        if browser == "chrome": return ChromeDriverManager().install()
        return GeckoDriverManager().install()
    except Exception as e:
        raise RuntimeError(f"Erro ao obter driver: {e}") from e

def get_browser_usage(proc_name):
    """Filtra estritamente as métricas definidas nos slides acadêmicos."""
    cpu_total = 0.0
    sys_time = 0.0
    ctx_switches = 0
    ram_rss = 0.0

    for proc in psutil.process_iter(['name', 'cpu_percent', 'cpu_times', 'memory_info', 'num_ctx_switches']):
        try:
            if proc_name in proc.info['name'].lower():
                cpu_total += proc.info.get('cpu_percent', 0)
                
                c_times = proc.info.get('cpu_times')
                if c_times:
                    sys_time += getattr(c_times, 'system', 0)
                
                c_switches = proc.info.get('num_ctx_switches')
                if c_switches:
                    ctx_switches += getattr(c_switches, 'voluntary', 0) + getattr(c_switches, 'involuntary', 0)

                mem = proc.info.get('memory_info')
                if mem:
                    ram_rss += getattr(mem, 'rss', 0) / (1024 * 1024)

        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            continue

    return (cpu_total, sys_time, ctx_switches, ram_rss)

def collect_metrics(browser_name, output_file):
    global monitoring_active, current_tabs
    proc_target = "chrome" if "chrome" in browser_name.lower() else "firefox"

    with open(output_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        # Cabeçalho estrito baseado nos slides fornecidos
        writer.writerow(["Tempo", "Abas", "CPU_Agregado", "System_Time", "Context_Switches", "RAM_RSS_MB"])
        start_time = time.time()
        
        while monitoring_active:
            elapsed = time.time() - start_time
            if elapsed >= TEST_DURATION_SEC:
                break
            metrics = get_browser_usage(proc_target)
            writer.writerow([int(elapsed), current_tabs, *metrics])
            time.sleep(sampling_interval)

def resolve_local_pdf_url(pdf_name="50mb.pdf"):
    base_dir = Path(__file__).resolve().parent
    candidate_paths = [base_dir / "samples" / pdf_name, base_dir / pdf_name]
    for path in candidate_paths:
        if path.exists(): return path.resolve().as_uri()
    return None 

def run_stress_test(browser_name, num_hardware_threads, execution_id):
    global monitoring_active, current_tabs
    
    # Gerencia e cria a estrutura de pastas direta (Ex: resultados/chrome/cores_4/)
    target_dir = Path("resultados") / browser_name.lower() / f"cores_{num_hardware_threads}"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    csv_file = target_dir / f"exec_{execution_id}.csv"
    
    monitoring_active = False
    current_tabs = 0
    thread = None
    driver = None

    try:
        if browser_name == "chrome":
            opts = webdriver.ChromeOptions()
            opts.add_argument("--incognito")
            driver = build_chrome_driver(resolve_driver_path("chrome"), opts)
        else:
            opts = webdriver.FirefoxOptions()
            opts.add_argument("-private")
            driver = build_firefox_driver(resolve_driver_path("firefox"), opts)

        try: driver.maximize_window()
        except: pass

        driver.set_page_load_timeout(30) 

        # Afinidade de CPU
        browser_pid = driver.service.process.pid if hasattr(driver, 'service') else None
        if browser_pid:
            try:
                parent_proc = psutil.Process(browser_pid)
                available_cores = list(range(num_hardware_threads))
                parent_proc.cpu_affinity(available_cores)
                for child in parent_proc.children(recursive=True):
                    child.cpu_affinity(available_cores)
            except Exception:
                pass

        # Início da monitoração
        monitoring_active = True
        thread = threading.Thread(target=collect_metrics, args=(browser_name, csv_file))
        thread.start()

        urls = [
            resolve_local_pdf_url() or "https://pt.wikipedia.org/wiki/Sistema_operativo",
            "https://earth.google.com/web/",
            "https://www.youtube.com/watch?v=LXb3EKWsInQ",
            "https://webglsamples.org/aquarium/aquarium.html",
            "https://browserbench.org/Speedometer2.0/",
            "https://v8.github.io/web-tooling-benchmark/"
        ]

        print(f"[{browser_name.upper()} | CORES: {num_hardware_threads} | RUN {execution_id}/{TOTAL_EXECUCOES}] Executando...")
        
        i = 0
        start_stress = time.time()
        
        while time.time() - start_stress < TEST_DURATION_SEC:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            if swap.percent > 95.0:
                while time.time() - start_stress < TEST_DURATION_SEC:
                    time.sleep(1)
                break
                
            url = urls[i % len(urls)]
            
            try:
                if i == 0:
                    driver.get(url)
                else:
                    driver.execute_script("window.open('about:blank', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.get(url)
                    
                current_tabs += 1
                time.sleep(3)
                i += 1
                
            except selenium.common.exceptions.TimeoutException:
                while time.time() - start_stress < TEST_DURATION_SEC:
                    time.sleep(1)
                break
            except Exception:
                while time.time() - start_stress < TEST_DURATION_SEC:
                    time.sleep(1)
                break

    except Exception as e:
        print(f"[ERRO] {browser_name}: {e}")
    finally:
        monitoring_active = False
        if thread is not None: thread.join()
        if driver is not None:
            try: driver.quit()
            except: pass

def generate_visual_report_scaling(thread_limits, browsers):
    """Gera o gráfico com base na nova estrutura de pastas."""
    plt.style.use('grayscale')
    styles = {
        "chrome": {"color": "black", "linestyle": "-", "marker": "o", "markersize": 6},
        "firefox": {"color": "dimgray", "linestyle": "--", "marker": "s", "markersize": 6}
    }

    fig, ax = plt.subplots(figsize=(8, 6))

    for browser in browsers:
        mean_max_sys_times = []
        for cores in thread_limits:
            peak_sys_times_in_runs = []
            
            for exec_id in range(1, TOTAL_EXECUCOES + 1):
                file = Path("resultados") / browser / f"cores_{cores}" / f"exec_{exec_id}.csv"
                max_sys_time = 0.0
                
                if file.exists():
                    with open(file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            sys_time = float(row['System_Time'])
                            if sys_time > max_sys_time:
                                max_sys_time = sys_time
                    peak_sys_times_in_runs.append(max_sys_time)
            
            if peak_sys_times_in_runs:
                mean_max_sys_times.append(sum(peak_sys_times_in_runs) / len(peak_sys_times_in_runs))
            else:
                mean_max_sys_times.append(0.0)

        ax.plot(thread_limits, mean_max_sys_times, label=browser.capitalize(), **styles[browser])

    ax.set_xticks(thread_limits)
    ax.set_xlabel("Threads de Hardware (Afinidade)")
    ax.set_ylabel("Média dos Picos de System Time (Segundos)")
    ax.set_title("Eficiência de Escalonamento - Métricas de Kernel")
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend()

    plt.tight_layout()
    
    # Salva os relatórios na pasta de relatórios dedicada
    report_dir = Path("relatorios")
    report_dir.mkdir(exist_ok=True)
    plt.savefig(report_dir / "escalonamento.pdf", format='pdf', dpi=300)
    plt.savefig(report_dir / "escalonamento.png", dpi=300)

def deep_clean_environment():
    for proc in ["firefox", "chrome", "geckodriver", "chromedriver"]:
        os.system(f"pkill -9 -f {proc} > /dev/null 2>&1")
    os.system("rm -rf /tmp/rust_mozprofile* /tmp/webdriver-py*")
    os.system("sync")
    os.system("sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'")
    os.system("sudo swapoff -a && sudo swapon -a")
    time.sleep(2)

if __name__ == "__main__":
    print("[SO] Autentique o sudo para iniciar os testes:")
    os.system("sudo -v") 
    
    limites_de_threads = [4, 8, 12, 16, 20, 24, 28]
    navegadores = ["chrome", "firefox"]

    for browser in navegadores:
        for cores in limites_de_threads:
            for exec_id in range(1, TOTAL_EXECUCOES + 1):
                deep_clean_environment()
                run_stress_test(browser, num_hardware_threads=cores, execution_id=exec_id)
                time.sleep(5)

    generate_visual_report_scaling(limites_de_threads, navegadores)
    print("\n[FIM] Experimento concluído com sucesso.")