import os
import sqlite3
import pandas as pd


def carica_dati(csv_path):
    df = pd.read_csv(csv_path)
    print(df.head())
    print(df.columns.tolist())
    print(df["Indicatore"].unique())
    print(df["Territorio"].unique())
    print(df.shape)
    print(df.isnull().sum())
    print(df.duplicated().sum())
    return df


def pulisci_dati(df):
    df.drop_duplicates(inplace=True)
    df["Territorio"] = (
        df["Territorio"]
        .str.replace('"', "", regex=False)
        .str.strip("'")
        .str.strip()
    )
    print(df["Territorio"].unique())
    return df


def prepara_colonne(df):
    # selezione colonne utili e rinomina colonne TIME_PERIOD e DATA_TYPE
    df_pulito = df[
        ["Territorio", "DATA_TYPE", "TIME_PERIOD", "Osservazione"]
    ].rename(columns={"TIME_PERIOD": "Anno", "DATA_TYPE": "Stile"})
    df_pulito["Osservazione"] = pd.to_numeric(
        df_pulito["Osservazione"], errors="coerce"
    )
    print(df_pulito.head())
    print(df_pulito.dtypes)
    return df_pulito


def filtra_territori(df_pulito):
    # lista territori da escludere (ampiezze comunali + province autonome + nord/mezzogiorno)
    esclusi = [
        "Centro area metropolitana",
        "Periferia area metropolitana",
        "Fino a 2.000 ab.",
        "2.001 - 10.000 ab.",
        "10.001 - 50.000 ab.",
        "50.001 ab. e più",
        "Provincia Autonoma Bolzano / Bozen",
        "Provincia Autonoma Trento",
        "Nord",
        "Mezzogiorno",
    ]
    df_filtrato = df_pulito[~df_pulito["Territorio"].isin(esclusi)]
    print(df_filtrato["Territorio"].unique())
    print("Territori:", len(df_filtrato["Territorio"].unique()))
    assert (
        len(df_filtrato["Territorio"].unique()) == 26
    ), "Numero territori errato."
    return df_filtrato


def analizza_colazione(df_pulito):
    # percentuale media nazionale colazione adeguata
    colazione_adeguata = df_pulito[
        (df_pulito["Stile"] == "3_ADEQ_BREAK")
        & (df_pulito["Territorio"] == "Italia")
    ]["Osservazione"].mean()

    # percentuale media nazionale colazione latte e cibo
    colazione_latte_cibo = df_pulito[
        (df_pulito["Stile"] == "3_MILK_BREAK")
        & (df_pulito["Territorio"] == "Italia")
    ]["Osservazione"].mean()

    # rapporto colazione_adeguata e colazione_latte_cibo
    rapporto = (colazione_latte_cibo / colazione_adeguata) * 100
    print("Media nazionale colazione con latte e cibo:", colazione_latte_cibo)
    print("Incidenza in % sulla colazione adeguata:", rapporto)
    return colazione_adeguata, colazione_latte_cibo, rapporto


def analizza_macroaree(df_pulito):
    # lista macroaree
    macroaree = ["Nord-ovest", "Nord-est", "Centro", "Sud", "Isole"]
    df_macroaree = df_pulito[df_pulito["Territorio"].isin(macroaree)]
    print(df_macroaree["Territorio"].unique())
    print("Macroaree:", len(df_macroaree["Territorio"].unique()))

    # media per Stile e Territorio per ciascuna macroarea
    colazione_macroaree = (
        df_macroaree.groupby(["Territorio", "Stile"])["Osservazione"]
        .mean()
        .unstack()
    )
    print(colazione_macroaree)

    # rapporto colazione latte e cibo su colazione adeguata per ciascuna macroarea
    rapporto_colazione_macroaree = (
        colazione_macroaree["3_MILK_BREAK"] / colazione_macroaree["3_ADEQ_BREAK"]
    ) * 100
    print(rapporto_colazione_macroaree)
    return colazione_macroaree, rapporto_colazione_macroaree


def analizza_nord_sud(df_pulito):
    # territori nord e sud
    nord_sud = ["Nord", "Mezzogiorno"]
    df_nord_sud = df_pulito[df_pulito["Territorio"].isin(nord_sud)]
    print(df_nord_sud["Territorio"].unique())
    print("Territori nord e sud:", len(df_nord_sud["Territorio"].unique()))

    # media per Stile e Territorio nord e sud
    pranzo_nord_sud = (
        df_nord_sud.groupby(["Territorio", "Stile"])["Osservazione"]
        .mean()
        .unstack()
    )
    print(pranzo_nord_sud)

    # differenza pasto principale tra nord e sud
    differenza_pranzo_cena = (
        pranzo_nord_sud["3_MMEAL_LUNCH"] - pranzo_nord_sud["3_MMEAL_DIN"]
    )
    print(differenza_pranzo_cena)
    return df_nord_sud, pranzo_nord_sud, differenza_pranzo_cena


def carica_in_sql(conn, df_filtrato, df_nord_sud):
    # caricamento dati puliti
    df_filtrato.to_sql("abitudini", conn, if_exists="replace", index=False)

    # verifica caricamento sql
    verifica = pd.read_sql("SELECT COUNT(*) FROM abitudini", conn)
    print(verifica)

    # importo df_nord_sud in sql
    df_nord_sud.to_sql("nord_sud", conn, if_exists="replace", index=False)


def query_luogo_pranzo(conn):
    # luogo pranzo nord vs sud
    luogo_pranzo_nord_sud = pd.read_sql(
        """SELECT Territorio, Stile, AVG(Osservazione) FROM nord_sud
        WHERE Territorio IN ('Nord', 'Mezzogiorno')
        AND Stile IN ('3_LUNCH_HOME', '3_LUNCH_CAF', '3_LUNCH_REST', '3_LUNCH_CANT', '3_LUNCH_WORK')
        GROUP BY Territorio, Stile""",
        conn,
    )
    print(luogo_pranzo_nord_sud)
    return luogo_pranzo_nord_sud


def query_scostamento_regionale(conn):
    # media nazionale stili alimentari
    stili_alimentari_nazionali = pd.read_sql(
        "SELECT Territorio, Stile, AVG(Osservazione) FROM abitudini WHERE Territorio = 'Italia' GROUP BY Stile",
        conn,
    )
    print(stili_alimentari_nazionali)

    # media regionale stili alimentari (escludendo Italia e le 5 macroaree)
    stili_alimentari_regionali = pd.read_sql(
        """SELECT Territorio, Stile, AVG(Osservazione) FROM abitudini
        WHERE Territorio NOT IN ('Italia', 'Nord-ovest', 'Nord-est', 'Centro', 'Sud', 'Isole')
        GROUP BY Territorio, Stile""",
        conn,
    )
    print(stili_alimentari_regionali)

    # unione stili alimentari nazionali e regionali
    risultato = stili_alimentari_regionali.merge(
        stili_alimentari_nazionali, on="Stile"
    )
    print(risultato)

    # differenza in percentuale
    gap = (
        risultato["AVG(Osservazione)_x"] - risultato["AVG(Osservazione)_y"]
    )

    # gap con segno
    risultato["gap"] = gap

    # valore assoluto gap
    risultato["gap_assoluto"] = gap.abs()

    # ordine decrescente gap_assoluto
    scostamento_maggiore = risultato.sort_values(
        by="gap_assoluto", ascending=False
    )
    print(scostamento_maggiore)

    # pulizia scostamento_maggiore per powerbi
    scostamento_maggiore = scostamento_maggiore[
        [
            "Territorio_x",
            "Stile",
            "AVG(Osservazione)_x",
            "AVG(Osservazione)_y",
            "gap",
            "gap_assoluto",
        ]
    ].rename(
        columns={
            "Territorio_x": "Territorio",
            "AVG(Osservazione)_x": "Valore_Regionale",
            "AVG(Osservazione)_y": "Valore_Nazionale",
        }
    )
    return scostamento_maggiore


def query_variazioni_anno(conn):
    # variazioni stili alimentari e luoghi pranzo 2024 vs 2025
    variazioni = pd.read_sql(
        """SELECT a.Territorio, a.Stile, a.Osservazione AS anno_2024, b.Osservazione AS anno_2025,
        (b.Osservazione - a.Osservazione) AS variazione_anni
        FROM abitudini AS a
        JOIN abitudini AS b ON a.Territorio = b.Territorio AND a.Stile = b.Stile
        WHERE a.Anno = 2024 AND b.Anno = 2025""",
        conn,
    )
    print(variazioni.head(10))

    # variazioni in aumento 2024 vs 2025
    print(variazioni.sort_values(by="variazione_anni", ascending=False).head(10))

    # variazioni in calo 2024 vs 2025
    print(variazioni.sort_values(by="variazione_anni", ascending=True).head(10))

    return variazioni


def esporta_per_powerbi(
    colazione_macroaree,
    pranzo_nord_sud,
    luogo_pranzo_nord_sud,
    scostamento_maggiore,
    variazioni,
    df_pulito,
):
    os.makedirs("output", exist_ok=True)

    # stile alimentare nazionale
    df_italia = df_pulito[df_pulito["Territorio"] == "Italia"]
    stili_alimentari_italia = (
        df_italia.groupby(["Territorio", "Stile"])["Osservazione"]
        .mean()
        .unstack()
    )

    # esportazione csv per powerbi
    colazione_macroaree.to_csv(
        "output/colazione_macroaree.csv", sep=";", decimal=","
    )
    pranzo_nord_sud.to_csv("output/pranzo_nord_sud.csv", sep=";", decimal=",")
    luogo_pranzo_nord_sud.to_csv(
        "output/luogo_pranzo_nord_sud.csv", sep=";", decimal=","
    )
    scostamento_maggiore.to_csv(
        "output/scostamento_maggiore.csv", index=False, sep=";", decimal=","
    )
    variazioni.to_csv(
        "output/variazioni.csv", index=False, sep=";", decimal=","
    )
    stili_alimentari_italia.to_csv(
        "output/stili_alimentari_italia.csv", index=False, sep=";", decimal=","
    )


if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    csv_path = os.path.join(
        base_dir,
        "data",
        "Abitudini nei pasti - regioni e tipo di comune (IT1,83_85_DF_DCCV_AVQ_PERSONE1_239,1.0).csv",
    )
    df = carica_dati(csv_path)
    df = pulisci_dati(df)
    df_pulito = prepara_colonne(df)
    df_filtrato = filtra_territori(df_pulito)

    analizza_colazione(df_pulito)
    colazione_macroaree, _ = analizza_macroaree(df_pulito)
    df_nord_sud, pranzo_nord_sud, _ = analizza_nord_sud(df_pulito)

    # connessione database sql
    conn = sqlite3.connect("analisi_abitudini_alimentari_italia.db")
    carica_in_sql(conn, df_filtrato, df_nord_sud)

    luogo_pranzo_nord_sud = query_luogo_pranzo(conn)
    scostamento_maggiore = query_scostamento_regionale(conn)
    variazioni = query_variazioni_anno(conn)
    conn.close()

    esporta_per_powerbi(
        colazione_macroaree,
        pranzo_nord_sud,
        luogo_pranzo_nord_sud,
        scostamento_maggiore,
        variazioni,
        df_pulito,
    )
