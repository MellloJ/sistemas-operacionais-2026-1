import os
import glob
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

def plot_smoothed_by_core(base_results_folder="resultados", window_seconds=10, total_executions=30):
    # Configura o estilo acadêmico rigoroso (Preto e Branco / Tons de cinza)
    plt.style.use('grayscale')
    
    # Pasta de saída dedicada aos gráficos temporais
    output_folder = Path("relatorios") / "graficos_por_core"
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Mapeamento estrito das métricas baseado nos slides acadêmicos fornecidos
    metrics_titles = {
        "CPU_Agregado": "Consumo de CPU Agregado (%)",
        "System_Time": "Tempo de CPU em Modo Kernel (s)",
        "Context_Switches": "Trocas de Contexto (Context Switches)",
        "RAM_RSS_MB": "Ocupação de Memória Física (RSS em MB)"
    }

    lista_cores = [4, 8, 12, 16, 20, 24, 28]
    browsers = ["chrome", "firefox"]
    
    styles = {
        "chrome": {"color": "black", "linestyle": "-", "marker": "o", "markersize": 4},
        "firefox": {"color": "dimgray", "linestyle": "--", "marker": "s", "markersize": 4}
    }

    print(f"[SO] Iniciando consolidação e geração de gráficos temporais em: {output_folder}")

    for metric, title in metrics_titles.items():
        for core in lista_cores:
            fig, ax = plt.subplots(figsize=(7, 4.5))
            has_data = False
            
            for browser in browsers:
                # Caminho para a pasta do cenário específico (ex: resultados/chrome/cores_4/)
                core_folder = Path(base_results_folder) / browser / f"cores_{core}"
                
                if not core_folder.exists():
                    continue
                
                # Lista todas as execuções (exec_1.csv até exec_30.csv)
                csv_files = list(core_folder.glob("exec_*.csv"))
                if not csv_files:
                    continue
                
                # Dataframe temporário para acumular as rodadas
                all_runs_data = []
                
                for file_path in csv_files:
                    try:
                        df = pd.read_csv(file_path)
                        if metric in df.columns and "Tempo" in df.columns:
                            # Garante que estamos pegando apenas o limite do teste (180s)
                            df = df[df["Tempo"] < 180]
                            all_runs_data.append(df[["Tempo", metric]])
                    except Exception as e:
                        print(f"[AVISO] Erro ao ler {file_path.name}: {e}")
                
                if not all_runs_data:
                    continue
                
                # --- CONSOLIDAÇÃO DAS 30 EXECUÇÕES ---
                # Une todas as rodadas e tira a média segundo a segundo para criar o comportamento representativo
                combined_df = pd.concat(all_runs_data)
                df_mean = combined_df.groupby("Tempo").mean().reset_index()
                
                # --- SUAVIZAÇÃO DOS DADOS (MOVING AVERAGE) ---
                # Agrupa em blocos de tempo baseados no 'window_seconds'
                df_mean['Grupo_Tempo'] = df_mean['Tempo'] // window_seconds
                df_smoothed = df_mean.groupby('Grupo_Tempo').mean().reset_index()
                
                # Reconverte o eixo X para refletir o tempo real em segundos
                df_smoothed['Tempo_Real'] = df_smoothed['Grupo_Tempo'] * window_seconds
                
                # Configura espaçamento dos marcadores para evitar poluição visual
                markevery = max(1, len(df_smoothed) // 10)
                
                # Plota a curva consolidada do navegador
                ax.plot(
                    df_smoothed["Tempo_Real"], 
                    df_smoothed[metric], 
                    label=browser.capitalize(), 
                    markevery=markevery,
                    **styles[browser]
                )
                has_data = True
            
            # Se o cenário continha dados, salva o gráfico formatado externamente
            if has_data:
                ax.set_title(f"{title} - Restrito a {core} Cores\n(Média Consolidada de {total_executions} Execuções)")
                ax.set_xlabel("Tempo de Execução Decorrido (Segundos)")
                ax.set_ylabel(title.split("(")[-1].replace(")", "") if "(" in title else metric)
                ax.grid(True, linestyle=':', alpha=0.6)
                ax.legend(loc="best")
                
                filename_base = f"{metric.lower()}_cores_{core:02d}"
                
                plt.tight_layout()
                plt.savefig(output_folder / f"{filename_base}.pdf", format='pdf', dpi=300)
                plt.savefig(output_folder / f"{filename_base}.png", dpi=300)
                plt.close()
                
    print(f"\n[SUCESSO] Todos os gráficos baseados nas {total_executions} rodadas foram gerados!")

if __name__ == "__main__":
    # Executa apontando para a pasta raiz criada pelo script de estresse
    plot_smoothed_by_core(base_results_folder="resultados", window_seconds=10, total_executions=30)