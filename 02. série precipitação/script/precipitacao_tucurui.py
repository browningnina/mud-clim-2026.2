# Marina Browning - 120056058

# Dados de precipitação da estação pluviométrica TUCURUÍ, localizada no estado do Pará, Brasil.
# Fonte: Hidroweb - ANA (Agência Nacional de Águas e Saneamento Básico)
# Código da Estação pluviométrica TUCURUÍ: 349000
# Coordenadas: lat -3.7603 lon -49.6667
# Período contemplado: 10/1995 a 07/2015

#%%
# importações
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# path 
path_precipitacao = r"C:\Users\marin\Projetos\mud-clim-2026.2\02. série precipitação\excel\349000_Chuvas.csv"
            
#%%
from tabulate import tabulate
# Leitura
# a coluna "TotalAnual" teve que ser removida pois ela começa a ser preenchida a partir da linha 368, o que estava gerando erro na leitrua do csv
df = pd.read_csv(
    path_precipitacao,
    encoding="ISO-8859-1",
    decimal = ",",
    sep=";",
    index_col="Data",
    header = 10,
    usecols=lambda col: col != "TotalAnual"
    )

print(df.columns.tolist())
print(tabulate(df.head(), headers='keys', tablefmt='psql'))
#%%
# Converter o índice para datetime
df.index = pd.to_datetime(
    df.index,
    format="%d/%m/%Y"
)

# Ordenar cronologicamente
df = df.sort_index()

# Criar ano e mês
df["Ano"] = df.index.year
df["Mes"] = df.index.month

#%%
# identificando as colunas de chuva diaria 
import re

colunas_chuva = [
    col for col in df.columns
    if re.fullmatch(r"Chuva\d{2}", str(col))
]
print(colunas_chuva)

def preencher_chuva_na(
    df,
    colunas,
    inicio="1996-07-01",
    fim="1999-02-01",
    random_state=42,
):
    """Preenche a lacuna no formato mensal original do HidroWeb.

    O valor de cada dia é sorteado, com reposição, da distribuição observada
    no mesmo mês em outros anos fora da lacuna. Isso preserva a sazonalidade,
    a frequência de dias secos e os eventos intensos sem interpolação linear.
    """
    inicio = pd.Timestamp(inicio)
    fim = pd.Timestamp(fim)
    if inicio.day != 1 or fim.day != 1 or inicio > fim:
        raise ValueError("inicio e fim devem ser o primeiro dia de um mês.")

    resultado = df.copy()
    resultado.index = pd.to_datetime(resultado.index)
    resultado.loc[:, colunas] = (
        resultado.loc[:, colunas]
        .replace(r"^\s*$", np.nan, regex=True)
        .replace(["n/a", "N/A", "NaN"], np.nan)
        .apply(pd.to_numeric, errors="coerce")
    )

    meses_lacuna = pd.date_range(inicio, fim, freq="MS")
    indice_original = resultado.index
    meses_novos = meses_lacuna[~meses_lacuna.isin(indice_original)]
    if len(meses_novos) > 0:
        novas_linhas = pd.DataFrame(
            index=meses_novos,
            columns=resultado.columns,
        )
        resultado = pd.concat([resultado, novas_linhas], axis=0)
    resultado = resultado.sort_index()
    resultado.index.name = df.index.name or "Data"

    valores = (
        df.loc[:, colunas]
        .replace(r"^\s*$", np.nan, regex=True)
        .replace(["n/a", "N/A", "NaN"], np.nan)
        .apply(pd.to_numeric, errors="coerce")
    )
    valores.index = indice_original
    # Duplicatas do HidroWeb são mantidas no resultado, mas uma única
    # observação por mês é usada para calcular a distribuição histórica.
    valores = valores.groupby(level=0).first()
    fora_lacuna = ~valores.index.isin(meses_lacuna)
    rng = np.random.default_rng(random_state)
    historico = {}

    for mes in range(1, 13):
        linhas_mes = valores.loc[fora_lacuna & (valores.index.month == mes)]
        historico[mes] = {
            coluna: linhas_mes[coluna].dropna().to_numpy()
            for coluna in colunas
        }
        if not any(amostras.size for amostras in historico[mes].values()):
            raise ValueError(f"Não há dados históricos para o mês {mes}.")

        historico[mes]["_mensal"] = (
            linhas_mes[colunas].stack().dropna().to_numpy()
        )

    resultado["DadoSintetico"] = False
    for data in meses_lacuna:
        # Meses que já existem na série original não são alterados.
        if data in indice_original:
            continue

        linha_sintetica = pd.Series(
            index=resultado.columns,
            name=data,
            dtype=object,
        )
        linha_sintetica.loc[:] = np.nan
        linha_sintetica["DadoSintetico"] = True
        dias_no_mes = data.days_in_month
        for dia in range(1, 32):
            coluna = f"Chuva{dia:02d}"
            if coluna not in colunas:
                continue

            if dia > dias_no_mes:
                continue

            amostras = historico[data.month][coluna]
            if amostras.size == 0:
                amostras = historico[data.month]["_mensal"]
            linha_sintetica[coluna] = max(
                0.0, float(rng.choice(amostras))
            )
        resultado = pd.concat(
            [resultado, linha_sintetica.to_frame().T],
            axis=0,
        )

    resultado = resultado.sort_index()

    if "Ano" in resultado.columns:
        resultado["Ano"] = resultado.index.year
    if "Mes" in resultado.columns:
        resultado["Mes"] = resultado.index.month
    return resultado


#%% avaliacao de duplicadas 
print("Linhas:", len(df))
print("Datas únicas:", df.index.nunique())
print("Datas duplicadas:", df.index.duplicated().sum())

duplicadas = df.index.duplicated(keep=False)

print(
    df.loc[duplicadas, 
           ["EstacaoCodigo", "NivelConsistencia", "TipoMedicaoChuvas", "Total"]]
    .sort_index()
)
#%%

'''  foi avaliado que as duplicadas são referentes a mesma data 
    mas com diferentes niveis de consistencia, 
    irei priorizar o tipo 1 que é o que mais tem dados
'''

def filtrar_consistencia_1(df):
    print("Nível de consistência:")
    print(df["NivelConsistencia"].value_counts().sort_index())

    df_filtrado = df[
        (df["NivelConsistencia"] == 1)
        | (df["NivelConsistencia"].isnull())
    ].copy()

    print(f"\nTotal de registros antes do filtro: {len(df)}")
    print(f"Total de registros com consistência 1: {len(df_filtrado)}")

    return df_filtrado
df_consistente = filtrar_consistencia_1(df)
df_consistente = preencher_chuva_na(
    df_consistente,
    colunas_chuva,
    inicio="1996-07-01",
    fim="1999-02-01",
    random_state=42,
)
# %%
# Transformando a tabela mensal em série diária.
dias = np.array([int(coluna[-2:]) for coluna in colunas_chuva])
datas_mensais = np.repeat(
    df_consistente.index.to_numpy(),
    len(colunas_chuva),
)
datas_diarias = pd.to_datetime(
    {
        "year": pd.DatetimeIndex(datas_mensais).year,
        "month": pd.DatetimeIndex(datas_mensais).month,
        "day": np.tile(dias, len(df_consistente)),
    },
    errors="coerce",
)
serie_diaria = pd.DataFrame(
    {
        "precipitacao": pd.to_numeric(
            df_consistente[colunas_chuva].to_numpy().ravel(),
            errors="coerce",
        ),
        "sintetica": np.repeat(
            df_consistente["DadoSintetico"].to_numpy(),
            len(colunas_chuva),
        ),
    },
    index=datas_diarias,
).dropna(subset=["precipitacao"])
serie_diaria = serie_diaria.sort_index()

# Mantém apenas datas válidas e destaca a lacuna preenchida.
serie_diaria = serie_diaria.loc[serie_diaria.index.notna()]
periodo_sintetico = (
    (serie_diaria.index >= pd.Timestamp("1996-07-01"))
    & (serie_diaria.index <= pd.Timestamp("1999-02-28"))
    & serie_diaria["sintetica"]
)

plt.figure(figsize=(15, 5))
plt.plot(
    serie_diaria.index,
    serie_diaria["precipitacao"],
    # color="0.65",
    linewidth=0.7,
    label="Dados observados",
)
plt.plot(
    serie_diaria.index[periodo_sintetico],
    serie_diaria.loc[periodo_sintetico, "precipitacao"],
    # color="tab:orange",
    linewidth=0.8,
    label="Dados sintéticos",
)
# plt.axvspan(
#     pd.Timestamp("1996-07-01"),
#     pd.Timestamp("1999-02-28"),
#     # color="tab:orange",
#     alpha=0.12,
# )
plt.xlabel("Data")
plt.ylabel("Precipitação (mm)")
plt.title("Série diária de precipitação — Estação TUCURUÍ")
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.show()

#%% Comparação da tendência em diferentes janelas temporais
serie_avaliacao = serie_diaria["precipitacao"].astype(float).sort_index()
totais_anuais_tendencia = serie_avaliacao.resample("YS").sum(min_count=1).dropna()
data_final = totais_anuais_tendencia.index.max()
limites_janelas = {
    "Série completa": totais_anuais_tendencia.index.min(),
    "Últimos 30 anos": data_final - pd.DateOffset(years=30),
    "Últimos 20 anos": data_final - pd.DateOffset(years=20),
    "Últimos 10 anos": data_final - pd.DateOffset(years=10),
}

resultados_tendencia = []
fig, eixos = plt.subplots(2, 2, figsize=(15, 9), sharey=True)

for eixo, (nome_janela, limite_inicial) in zip(
    eixos.ravel(),
    limites_janelas.items(),
):
    dados_janela = totais_anuais_tendencia[
        totais_anuais_tendencia.index >= limite_inicial
    ]
    anos_janela = dados_janela.index.year.to_numpy()
    valores_janela = dados_janela.to_numpy()

    if len(dados_janela) >= 2:
        coeficiente = np.polyfit(anos_janela, valores_janela, 1)
        tendencia = np.polyval(coeficiente, anos_janela)
        resultados_tendencia.append(
            {
                "janela": nome_janela,
                "ano_inicial": anos_janela.min(),
                "ano_final": anos_janela.max(),
                "tendencia_mm_por_ano": coeficiente[0],
            }
        )
        eixo.plot(
            dados_janela.index,
            valores_janela,
            marker="o",
            linewidth=1,
            label="Total anual",
        )
        eixo.plot(
            dados_janela.index,
            tendencia,
            linestyle="--",
            linewidth=1.5,
            label=f"Tendência: {coeficiente[0]:.2f} mm/ano",
        )
    else:
        eixo.text(
            0.5,
            0.5,
            "Dados insuficientes para tendência",
            ha="center",
            va="center",
            transform=eixo.transAxes,
        )

    eixo.set_title(nome_janela)
    eixo.set_xlabel("Ano")
    eixo.set_ylabel("Precipitação anual (mm)")
    eixo.grid(alpha=0.3)
    eixo.legend()

print("\nComparação das tendências por janela temporal:")
print(pd.DataFrame(resultados_tendencia))
fig.suptitle("Tendência da precipitação em diferentes períodos")
plt.tight_layout()
plt.show()

#%% Avaliação de valores extremos por mês e por ano
serie_avaliacao = serie_diaria["precipitacao"].astype(float).sort_index()
dados_boxplot = pd.DataFrame(
    {
        "precipitacao": serie_avaliacao,
        "mes": serie_avaliacao.index.month,
        "ano": serie_avaliacao.index.year,
    },
    index=serie_avaliacao.index,
)


def resumir_extremos_por_grupo(dados, grupo):
    """Calcula limites do IQR e quantidade de extremos por grupo."""
    resumo = []
    for identificador, valores in dados.groupby(grupo)["precipitacao"]:
        q1_grupo = valores.quantile(0.25)
        q3_grupo = valores.quantile(0.75)
        iqr_grupo = q3_grupo - q1_grupo
        limite_superior = q3_grupo + 1.5 * iqr_grupo
        extremos_grupo = valores[valores > limite_superior]
        resumo.append(
            {
                grupo: identificador,
                "q1": q1_grupo,
                "q3": q3_grupo,
                "limite_superior": limite_superior,
                "quantidade_extremos": len(extremos_grupo),
                "maior_valor": valores.max(),
            }
        )
    return pd.DataFrame(resumo).set_index(grupo)


extremos_por_mes = resumir_extremos_por_grupo(dados_boxplot, "mes")
extremos_por_ano = resumir_extremos_por_grupo(dados_boxplot, "ano")

print("\nExtremos por mês:")
print(extremos_por_mes)
print("\nExtremos por ano:")
print(extremos_por_ano)

fig, eixos = plt.subplots(2, 1, figsize=(15, 10))
dados_boxplot.boxplot(
    column="precipitacao",
    by="mes",
    ax=eixos[0],
    grid=False,
    showfliers=True,
)
eixos[0].set_title("Boxplot da precipitação diária por mês")
eixos[0].set_xlabel("Mês")
eixos[0].set_ylabel("Precipitação (mm)")

dados_boxplot.boxplot(
    column="precipitacao",
    by="ano",
    ax=eixos[1],
    grid=False,
    showfliers=True,
)
eixos[1].set_title("Boxplot da precipitação diária por ano")
eixos[1].set_xlabel("Ano")
eixos[1].set_ylabel("Precipitação (mm)")
eixos[1].tick_params(axis="x", rotation=45)

fig.suptitle("Distribuição e valores extremos da precipitação")
plt.tight_layout()
plt.show()

#%% Avaliação de variabilidade, valores extremos e mudanças aparentes
serie_avaliacao = serie_diaria["precipitacao"].astype(float).sort_index()

# Variabilidade: desvio-padrão e coeficiente de variação por ano.
avaliacao_anual = serie_avaliacao.resample("YS").agg(
    total="sum",
    media="mean",
    mediana="median",
    desvio_padrao="std",
    dias_chuvosos=lambda valores: (valores > 0).sum(),
)
avaliacao_anual["coeficiente_variacao"] = (
    avaliacao_anual["desvio_padrao"] / avaliacao_anual["media"].replace(0, np.nan)
)
print("\nVariabilidade anual:")
print(avaliacao_anual)

# Extremos pelo percentil 99 e pelo limite superior do IQR.
q1 = serie_avaliacao.quantile(0.25)
q3 = serie_avaliacao.quantile(0.75)
iqr = q3 - q1
limite_extremo = q3 + 1.5 * iqr
percentil_99 = serie_avaliacao.quantile(0.99)
extremos = serie_avaliacao[
    serie_avaliacao >= max(limite_extremo, percentil_99)
].sort_values(ascending=False)

print("\nLimites para valores extremos:")
print(f"Q1: {q1:.2f} mm | Q3: {q3:.2f} mm | IQR: {iqr:.2f} mm")
print(f"Limite superior do IQR: {limite_extremo:.2f} mm")
print(f"Percentil 99: {percentil_99:.2f} mm")
print("\nMaiores eventos de precipitação:")
print(extremos.head(20))

# Mudanças aparentes: médias móveis e tendência linear anual.
media_movel_90 = serie_avaliacao.rolling("90D", min_periods=30).mean()
totais_mensais = serie_avaliacao.resample("MS").sum(min_count=1)

anos = avaliacao_anual.index.year.to_numpy()
totais = avaliacao_anual["total"].to_numpy()
validos = ~np.isnan(totais)
coeficiente_tendencia = np.polyfit(anos[validos], totais[validos], 1)[0]
print(
    "\nMudança aparente no total anual: "
    f"{coeficiente_tendencia:.2f} mm/ano"
)
print("\nMédia móvel anual (12 meses):")

fig, eixos = plt.subplots(2, 1, figsize=(15, 9), sharex=False)
eixos[0].plot(
    avaliacao_anual.index,
    avaliacao_anual["total"],
    marker="o",
    linewidth=1,
    label="Precipitação anual",
)
eixos[0].plot(
    avaliacao_anual.index,
    np.polyval(np.polyfit(anos[validos], totais[validos], 1), anos),
    linestyle="--",
    label="Tendência linear aparente",
)

eixos[0].set_ylabel("Precipitação anual (mm)")
eixos[0].set_title("Mudanças aparentes no total anual")
eixos[0].grid(alpha=0.3)
eixos[0].legend()

eixos[1].plot(
    serie_avaliacao.index,
    media_movel_90,
    linewidth=0.8,
    label="Média móvel de 90 dias",
)
eixos[1].scatter(
    extremos.index,
    extremos.values,
    color="tab:red",
    s=12,
    label="Valores extremos",
)
eixos[1].set_xlabel("Data")
eixos[1].set_ylabel("Precipitação média (mm)")
eixos[1].set_title("Variabilidade e extremos ao longo do tempo")
eixos[1].grid(alpha=0.3)
eixos[1].legend()
plt.tight_layout()
plt.show()

#%% Avaliação da variabilidade em relação à tendência
anos_validos = anos[validos]
totais_validos = totais[validos]
ajuste_tendencia = np.polyval(
    np.polyfit(anos_validos, totais_validos, 1),
    anos_validos,
)
residuos_tendencia = totais_validos - ajuste_tendencia
desvio_padrao_anual = np.std(totais_validos, ddof=1)
desvio_padrao_residuos = np.std(residuos_tendencia, ddof=1)
variacao_explicada_tendencia = abs(
    ajuste_tendencia[-1] - ajuste_tendencia[0]
)
razao_variabilidade_tendencia = (
    desvio_padrao_residuos / variacao_explicada_tendencia
    if variacao_explicada_tendencia > 0
    else np.inf
)

if razao_variabilidade_tendencia > 1:
    interpretacao_variabilidade = (
        "A variabilidade é grande em relação à tendência: "
        "as oscilações anuais superam a mudança linear estimada."
    )
else:
    interpretacao_variabilidade = (
        "A variabilidade é pequena em relação à tendência: "
        "a mudança linear estimada supera as oscilações anuais."
    )

print("\nVariabilidade em relação à tendência:")
print(f"Desvio-padrão dos totais anuais: {desvio_padrao_anual:.2f} mm")
print(f"Desvio-padrão dos resíduos: {desvio_padrao_residuos:.2f} mm")
print(
    "Variação explicada pela tendência no período: "
    f"{variacao_explicada_tendencia:.2f} mm"
)
print(
    "Razão variabilidade/tendência: "
    f"{razao_variabilidade_tendencia:.2f}"
)
print(interpretacao_variabilidade)

fig, eixos = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
eixos[0].plot(
    anos_validos,
    totais_validos,
    marker="o",
    label="Total anual",
)
eixos[0].plot(
    anos_validos,
    ajuste_tendencia,
    linestyle="--",
    label="Tendência linear",
)
eixos[0].set_ylabel("Precipitação anual (mm)")
eixos[0].set_title("Variabilidade observada e tendência")
eixos[0].grid(alpha=0.3)
eixos[0].legend()

eixos[1].axhline(0, color="black", linewidth=0.8)
eixos[1].bar(anos_validos, residuos_tendencia, width=0.8)
eixos[1].set_xlabel("Ano")
eixos[1].set_ylabel("Resíduo (mm)")
eixos[1].set_title("Oscilações anuais em torno da tendência")
eixos[1].grid(alpha=0.3)
plt.tight_layout()
plt.show()

#%% Decomposição sazonal em ciclos de 12 meses
from statsmodels.tsa.seasonal import seasonal_decompose

serie_mensal = (
    serie_avaliacao.resample("MS")
    .sum(min_count=1)
    .dropna()
)
decomposicao = seasonal_decompose(
    serie_mensal,
    model="additive",
    period=12,
    extrapolate_trend="freq",
)

print("\nComponente sazonal média por mês:")
print(decomposicao.seasonal.groupby(decomposicao.seasonal.index.month).mean())

fig, eixos = plt.subplots(4, 1, figsize=(15, 11), sharex=True)
eixos[0].plot(serie_mensal, color="0.35")
eixos[0].set_title("Série mensal de precipitação")
eixos[1].plot(decomposicao.trend, color="tab:blue")
eixos[1].set_title("Tendência")
eixos[2].plot(decomposicao.seasonal, color="tab:green")
eixos[2].set_title("Sazonalidade — ciclo de 12 meses")
eixos[3].plot(decomposicao.resid, color="tab:red")
eixos[3].set_title("Resíduo")
for eixo in eixos:
    eixo.grid(alpha=0.3)
    eixo.set_ylabel("mm")
eixos[-1].set_xlabel("Data")
plt.tight_layout()
plt.show()

#%% Exportação da série preenchida
caminho_saida = (
    r"C:\Users\marin\Projetos\mud-clim-2026.2"
    r"\02. série precipitação\excel\349000_Chuvas_preenchida.csv"
)
df_consistente.to_csv(
    caminho_saida,
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    index_label="Data",
)
print(f"\nSérie preenchida exportada para: {caminho_saida}")
