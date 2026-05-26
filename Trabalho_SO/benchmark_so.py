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
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager


SELENIUM_MAJOR = int(selenium.__version__.split(".")[0])


def build_chrome_driver(driver_path, options):
    if SELENIUM_MAJOR >= 4:
        return webdriver.Chrome(service=ChromeService(driver_path), options=options)
    return webdriver.Chrome(executable_path=driver_path, options=options)


def build_firefox_driver(driver_path, options):
    if SELENIUM_MAJOR >= 4:
        return webdriver.Firefox(service=FirefoxService(driver_path), options=options)
    return webdriver.Firefox(executable_path=driver_path, options=options)


def build_edge_driver(driver_path, options):
    if not hasattr(webdriver, "Edge"):
        raise RuntimeError("Selenium instalado nao oferece webdriver.Edge neste ambiente.")
    if SELENIUM_MAJOR >= 4:
        return webdriver.Edge(service=EdgeService(driver_path), options=options)
    # Selenium 3 possui suporte inconsistente ao Edge no Linux.
    raise RuntimeError("Edge nao suportado com Selenium 3 neste ambiente.")


def resolve_driver_path(browser_name):
    """Usa driver local quando possivel e evita dependencia obrigatoria de internet."""
    base_dir = Path(__file__).resolve().parent
    driver_by_browser = {
        "chrome": "chromedriver",
        "firefox": "geckodriver",
        "edge": "msedgedriver",
    }
    local_project_driver = {
        "chrome": base_dir / "tools" / "chromedriver" / "chromedriver",
        "firefox": base_dir / "tools" / "geckodriver" / "geckodriver",
        "edge": base_dir / "tools" / "msedgedriver" / "msedgedriver",
    }
    browser = browser_name.lower()
    candidate = local_project_driver[browser]
    if candidate.exists() and candidate.is_file():
        print(f"[{browser.upper()}] Driver local do projeto detectado: {candidate}")
        return str(candidate)

    local_driver = shutil.which(driver_by_browser[browser])
    if local_driver:
        print(f"[{browser.upper()}] Driver local detectado: {local_driver}")
        return local_driver

    print(f"[{browser.upper()}] Driver local nao encontrado. Tentando webdriver_manager...")
    try:
        if browser == "chrome":
            return ChromeDriverManager().install()
        if browser == "firefox":
            return GeckoDriverManager().install()
        return EdgeChromiumDriverManager().install()
    except Exception as e:
        raise RuntimeError(
            f"Nao foi possivel obter o driver do {browser}. "
            "Sem internet, instale o driver local e deixe-o no PATH. "
            f"Erro original: {e}"
        ) from e

# --- CONFIGURAÇÕES DE MONITORAMENTO ---
sampling_interval = 1.0  
monitoring_active = False

def get_browser_usage(proc_name):
    """Soma consumo de todos os processos filhos via psutil."""
    cpu_total = 0.0
    ram_total = 0.0
    for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
        try:
            # O Edge no Linux pode aparecer como 'msedge'
            if proc_name in proc.info['name'].lower():
                cpu_total += proc.info['cpu_percent']
                ram_total += proc.info['memory_info'].rss / (1024 * 1024) 
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return cpu_total, ram_total

def collect_metrics(browser_name, output_file):
    global monitoring_active
    # Define o alvo do processo baseado no navegador
    if "chrome" in browser_name.lower(): proc_target = "chrome"
    elif "edge" in browser_name.lower(): proc_target = "msedge"
    else: proc_target = "firefox"

    with open(output_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Tempo", "CPU", "RAM"])
        start_time = time.time()
        while monitoring_active:
            t = int(time.time() - start_time)
            cpu, ram = get_browser_usage(proc_target)
            writer.writerow([t, cpu, ram])
            time.sleep(sampling_interval)

def resolve_local_pdf_url(pdf_name="50mb.pdf"):
    base_dir = Path(__file__).resolve().parent
    candidate_paths = [base_dir / "samples" / pdf_name, base_dir / pdf_name]
    for path in candidate_paths:
        if path.exists(): return path.resolve().as_uri()
    raise FileNotFoundError(f"Arquivo {pdf_name} nao encontrado.")

def run_stress_test(browser_name):
    global monitoring_active
    csv_file = f"dados_{browser_name}.csv"
    monitoring_active = False
    thread = None
    driver = None

    try:
        if browser_name == "chrome":
            opts = webdriver.ChromeOptions()
            opts.add_argument("--incognito")
            driver_path = resolve_driver_path("chrome")
            driver = build_chrome_driver(driver_path, opts)
        elif browser_name == "edge":
            if not hasattr(webdriver, "EdgeOptions"):
                raise RuntimeError("EdgeOptions indisponivel na versao atual do Selenium.")
            opts = webdriver.EdgeOptions()
            opts.add_argument("-inprivate")
            driver_path = resolve_driver_path("edge")
            driver = build_edge_driver(driver_path, opts)
        else:
            opts = webdriver.FirefoxOptions()
            opts.add_argument("-private")
            profile_path = Path(os.getcwd()) / "firefox_profile"
            profile_path.mkdir(parents=True, exist_ok=True)
            opts.add_argument("-profile")
            opts.add_argument(str(profile_path))
            driver_path = resolve_driver_path("firefox")
            driver = build_firefox_driver(driver_path, opts)

        monitoring_active = True
        thread = threading.Thread(target=collect_metrics, args=(browser_name, csv_file))
        thread.start()

        urls = [
            resolve_local_pdf_url(),
            "https://earth.google.com/web/",
            "https://www.youtube.com/watch?v=LXb3EKWsInQ",
            "https://webglsamples.org/aquarium/aquarium.html",
            "https://browserbench.org/Speedometer2.0/",
            "https://v8.github.io/web-tooling-benchmark/",
            "https://www.figma.com/",
            "https://threejs.org/examples/webgl_animation_keyframes.html",
            "https://edition.cnn.com/",
            "https://www.speedtest.net/"
        ]

        print(f"[{browser_name.upper()}] Disparando carga nos 28 threads...")
        for i, url in enumerate(urls):
            if i == 0: driver.get(url)
            else: driver.execute_script(f"window.open('{url}');")
            time.sleep(1.5)

        time.sleep(100)
    except Exception as e:
        print(f"[ERRO] Falha no teste {browser_name}: {e}")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        monitoring_active = False
        if thread is not None:
            thread.join()

def generate_visual_report():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    for browser in ["chrome", "firefox", "edge"]:
        file = f"dados_{browser}.csv"
        if os.path.exists(file):
            t, cpu, ram = [], [], []
            with open(file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    t.append(int(row['Tempo'])); cpu.append(float(row['CPU'])); ram.append(float(row['RAM']))
            ax1.plot(t, cpu, label=browser.upper()); ax2.plot(t, ram, label=browser.upper())

    ax1.set_title("Uso de CPU (%) - Analise Comparativa (3 Navegadores)"); ax1.legend()
    ax2.set_title("Uso de RAM (MB) - Analise Comparativa (3 Navegadores)"); ax2.set_xlabel("Tempo (s)"); ax2.legend()
    plt.tight_layout(); plt.savefig("grafico_performance_final.png")
    print("\n[SUCESSO] Relatorio visual gerado: grafico_performance_final.png")

def deep_clean_environment():
    print("[SO] Realizando limpeza de processos e arquivos temporarios...")
    for proc in ["firefox", "chrome", "msedge", "geckodriver", "chromedriver", "msedgedriver"]:
        os.system(f"pkill -9 -f {proc} > /dev/null 2>&1")
    os.system("rm -rf /tmp/rust_mozprofile* /tmp/webdriver-py*")
    time.sleep(2)

if __name__ == "__main__":
    deep_clean_environment()
    run_stress_test("edge")

    print("\nCooldown (30s)...")
    time.sleep(30)
    deep_clean_environment()
    run_stress_test("chrome")

    print("\nCooldown (30s)...")
    time.sleep(30)
    deep_clean_environment()
    run_stress_test("firefox")

    generate_visual_report()