from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.data import Data

import pandas as pd
import numpy as np
import re
import json
from typing import Any, Dict, List, Optional


# =========================
# Funções utilitárias (baseadas no seu código genérico)
# =========================
COLUNAS_MAPEAMENTO_BASE = {
    "termo": "Nome Coluna",
    "outro termo": "Outra Coluna",
    # O usuário pode sobrescrever / estender esse dicionário via entrada["colunas_mapeamento"]
}

def build_colunas_map(override: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    m = dict(COLUNAS_MAPEAMENTO_BASE)
    if isinstance(override, dict):
        m.update(override)
    # normaliza chaves para lower-case
    return {k.lower(): v for k, v in m.items()}


def normalizar_colunas(df: pd.DataFrame) -> Dict[str, str]:
    """Retorna mapping de nome_normalizado -> nome_real (preservando case)"""
    return {str(c).strip().lower(): c for c in df.columns}


def normalizar_coluna_para_busca(df: pd.DataFrame, coluna: str) -> Optional[str]:
    if coluna is None:
        return None
    for col in df.columns:
        if col.lower() == coluna.lower():
            return col
    return None


def mapear_coluna(coluna: Any, df_map: Dict[str, str], df: Optional[pd.DataFrame] = None, semantico: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Mapeia um nome "livre" para o nome real do DataFrame.
    Aceita string ou lista.
    Usa dicionário semântico (semantico) e df_map (normalizado).
    """
    if coluna is None:
        return None
    if isinstance(coluna, list):
        coluna = coluna[0] if coluna else None
    if coluna is None:
        return None
    key = str(coluna).strip().lower()

    # semântico
    if semantico and key in semantico:
        target = semantico[key]
        if df is not None:
            real = normalizar_coluna_para_busca(df, target)
            if real:
                return real
        return target

    # correspondência direta no map do df
    if key in df_map:
        return df_map[key]

    # substring em colunas normalizadas
    for k, v in df_map.items():
        if key in k:
            return v

    # tentativa direta no df (caso o usuário passe nome real)
    if df is not None:
        col_real = normalizar_coluna_para_busca(df, key)
        if col_real:
            return col_real

    return None


def parse_termos_texto(valor: Any) -> List[str]:
    return [t for t in re.split(r'[\s,;]+', str(valor).strip()) if t]


def detectar_comparacao_numerica(s: Any):
    """Detecta expressões como '> 5', '>=10', 'menor que 5', etc. Retorna (op, num) ou None"""
    s = str(s).strip().lower()
    m = re.match(r'^(>=|<=|==|!=|>|<|=)\s*([-+]?\d+(\.\d+)?)$', s)
    if m:
        op, num = m.group(1), float(m.group(2))
        if op == "=":
            op = "=="
        return op, num
    m3 = re.search(r'maior(?:es)? que\s*([-+]?\d+(?:\.\d+)?)', s)
    if m3:
        return ">", float(m3.group(1))
    m4 = re.search(r'menor(?:es)? que\s*([-+]?\d+(?:\.\d+)?)', s)
    if m4:
        return "<", float(m4.group(1))
    m5 = re.search(r'maior ou igual a\s*([-+]?\d+(?:\.\d+)?)', s)
    if m5:
        return ">=", float(m5.group(1))
    m6 = re.search(r'menor ou igual a\s*([-+]?\d+(?:\.\d+)?)', s)
    if m6:
        return "<=", float(m6.group(1))
    return None


def to_serializable(obj):
    """Transforma DataFrames / numpy / pandas types em tipos primitivos JSON-serializáveis"""
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, pd.Series):
        return obj.to_list()
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [to_serializable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    return obj


# =========================
# Função principal convertida (base do seu código genérico)
# =========================
def executar_pesquisa(entrada: dict,
                      arquivo_excel: str = "Planilha.xlsx",
                      aba: Optional[int] = None,
                      header_linha: int = 0) -> pd.DataFrame:
    """
    Entrada esperada (exemplos):
    {
      "colunas_mapeamento": {"sobreviveu": "Survived", ...},  # opcional
      "data": [{"column_name": "Sexo", "value": "female"}, ...],
      "special_conditions": ["Pclass == 1 and Fare > 50", ...],
      "operation": "mean",
      "column_operation": "Fare",
      "group_by": ["Sex"],
      "columns_to_show": ["Name","Fare"],
      "correlation": ["Age","Fare"],
      "comparisons": ["Fare","Survived"],
      "ranking": ["desc"],
      "limit": 5,
      "n": 5
    }
    """
    # --- leitura do arquivo ---
    try:
        df = pd.read_excel(arquivo_excel, sheet_name=aba or 0, header=header_linha)
    except FileNotFoundError:
        # retorna DataFrame vazio para compatibilidade
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    # limpeza/aglutinação de colunas
    df.columns = [str(c).strip() for c in df.columns]
    df_map = normalizar_colunas(df)

    # mapeamento semântico (possível override via entrada)
    semantico = build_colunas_map(entrada.get("colunas_mapeamento"))

    # filtro inicial (todas as linhas)
    filtro = pd.Series(True, index=df.index)

    # --- FILTROS SIMPLES (entrada["data"], "filters", "filtros") ---
    filtros_entrada = []
    for chave in ["data", "filter", "filters", "filtros"]:
        valor = entrada.get(chave)
        if isinstance(valor, list):
            filtros_entrada.extend(valor)

    # se special_conditions vier como string ou lista, empilha
    specials = entrada.get("special_conditions", []) or []
    if isinstance(specials, str):
        specials = [specials]
    for cond in specials:
        filtros_entrada.append({"column_name": None, "value": cond})

    # aplica cada filtro
    for item in filtros_entrada:
        coluna_input = item.get("column_name") or item.get("column")
        valor_input = item.get("value", "")
        coluna_real = mapear_coluna(coluna_input, df_map, df, semantico) if coluna_input else None

        # se valor for expressão do tipo numérico
        comp = detectar_comparacao_numerica(valor_input)
        if comp and coluna_real:
            op, num = comp
            col_num = pd.to_numeric(df[coluna_real], errors="coerce")
            if op == "==":
                filtro &= col_num == num
            elif op == "!=":
                filtro &= col_num != num
            elif op == ">":
                filtro &= col_num > num
            elif op == ">=":
                filtro &= col_num >= num
            elif op == "<":
                filtro &= col_num < num
            elif op == "<=":
                filtro &= col_num <= num
            continue

        # se coluna não informada mas valor possui expressão com coluna (ex: "Age > 30")
        if not coluna_real:
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*(==|=|!=|>=|<=|>|<)\s*['\"]?([^'\"]+)['\"]?", str(valor_input).strip())
            if m:
                col_name_candidate, op, val = m.groups()
                mapped_col = mapear_coluna(col_name_candidate, df_map, df, semantico)
                if mapped_col:
                    coluna_real = mapped_col
                    valor_input = f"{op}{val}"

        # se ainda sem coluna real -> tentar tratar expressão complexa (com colunas)
        if not coluna_real:
            vstr = str(valor_input).strip()
            # se tiver operadores lógicos ou python-like, tenta substituir tokens por df[...] e avaliar
            if re.search(r"[<>=!]| and | or ", vstr, flags=re.IGNORECASE):
                # construindo padrão de substituição com possíveis nomes (colunas reais + chaves semantico)
                nomes_possiveis = list(df.columns) + list(semantico.keys())
                padrao = r"\b(" + "|".join(re.escape(c) for c in nomes_possiveis) + r")\b"
                def substituir_token(match):
                    token = match.group(0)
                    mapped = mapear_coluna(token, df_map, df, semantico)
                    if mapped:
                        return f"df[{repr(mapped)}]"
                    # se token for um key semantico que não mapeou para coluna real, devolve token literal
                    return token
                expr = re.sub(padrao, substituir_token, vstr, flags=re.IGNORECASE)
                try:
                    filtro &= eval(expr, {"df": df, "np": np, "pd": pd})
                except Exception:
                    # se falhar, tenta busca textual fallback
                    pass
                continue

        # por fim, se temos coluna real: trata como texto / contains ou igualdade
        if coluna_real and coluna_real in df.columns:
            v = str(valor_input).strip()
            # caso valor seja operador-comparação (ex: ">=5")
            m2 = re.match(r'^(==|!=|>=|<=|>|<)\s*([-+]?\d+(\.\d+)?)$', v)
            if m2:
                op, num = m2.group(1), float(m2.group(2))
                col_num = pd.to_numeric(df[coluna_real], errors="coerce")
                if op == "==":
                    filtro &= col_num == num
                elif op == "!=":
                    filtro &= col_num != num
                elif op == ">":
                    filtro &= col_num > num
                elif op == ">=":
                    filtro &= col_num >= num
                elif op == "<":
                    filtro &= col_num < num
                elif op == "<=":
                    filtro &= col_num <= num
                continue

            # igualdade textual "==texto"
            if "==" in v:
                texto = v.split("==", 1)[-1].strip().strip("'\"").lower()
                filtro &= df[coluna_real].astype(str).str.lower() == texto
                continue

            # fallback: contains (palavras separadas)
            termos = parse_termos_texto(v)
            if termos:
                col_text = df[coluna_real].astype(str).str.lower()
                filtro_termos = pd.Series(False, index=df.index)
                for t in termos:
                    filtro_termos |= col_text.str.contains(str(t).lower(), na=False)
                filtro &= filtro_termos
                continue

    # aplica filtro no df
    df_filtrado = df.loc[filtro].copy()

    if df_filtrado.empty:
        return pd.DataFrame()

    # =========================
    # Operações
    # =========================
    oper = (entrada.get("operation") or "") or ""
    op_low = str(oper).strip().lower() if oper else ""

    # mapear coluna de operação
    col_op = entrada.get("column_operation")
    if isinstance(col_op, list):
        col_op = col_op[0] if col_op else None
    col_op_real = mapear_coluna(col_op, df_map, df, semantico) if col_op else None

    # columns to show
    cols_to_show = entrada.get("columns_to_show") or []
    cols_to_show_mapped = [mapear_coluna(c, df_map, df, semantico) for c in cols_to_show] if cols_to_show else []
    cols_to_show_mapped = [c for c in cols_to_show_mapped if c]

    # group_by mapeado
    group_by_list = entrada.get("group_by", []) or []
    if isinstance(group_by_list, (str, dict)):
        # garantir lista
        group_by_list = [group_by_list]
    group_by_cols = [mapear_coluna(c, df_map, df, semantico) for c in group_by_list if mapear_coluna(c, df_map, df, semantico)]
    group_by_cols = [c for c in group_by_cols if c]

    try:
        # Sem operação -> retornar df_filtrado (ou só colunas solicitadas)
        if not op_low:
            if cols_to_show_mapped:
                return df_filtrado[cols_to_show_mapped]
            return df_filtrado

        # COUNT
        if op_low in ["count", "contagem"]:
            if group_by_cols:
                return df_filtrado.groupby(group_by_cols).size().reset_index(name="contagem")
            return pd.DataFrame([{"contagem": len(df_filtrado)}])

        # PERCENT / PORCENTAGEM
        if op_low in ["porcentagem", "percent", "percentage", "percentual"]:
            total_geral = len(pd.read_excel(arquivo_excel, sheet_name=aba or 0, header=header_linha))
            total_filtrado = len(df_filtrado)
            if not group_by_cols:
                pct = (total_filtrado / total_geral) * 100 if total_geral else 0
                return pd.DataFrame([{"porcentagem": round(pct, 2), "total_filtrado": total_filtrado, "total_geral": total_geral}])
            # por grupo
            tot_por_grupo = df.groupby(group_by_cols).size().rename("total_no_grupo")
            filt_por_grupo = df_filtrado.groupby(group_by_cols).size().rename("filtrados_no_grupo")
            res = pd.concat([tot_por_grupo, filt_por_grupo], axis=1).fillna(0)
            res["porcentagem_no_grupo"] = (res["filtrados_no_grupo"] / res["total_no_grupo"] * 100).round(2)
            return res.reset_index()

        # MEAN / MEDIA
        if op_low in ["mean", "media"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                return pd.DataFrame()
            if group_by_cols:
                return df_filtrado.groupby(group_by_cols)[col_op_real].mean().reset_index(name=f"mean_{col_op_real}")
            return pd.DataFrame([{f"mean_{col_op_real}": df_filtrado[col_op_real].dropna().mean()}])

        # SUM
        if op_low in ["sum", "soma"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                return pd.DataFrame()
            return pd.DataFrame([{f"sum_{col_op_real}": df_filtrado[col_op_real].dropna().sum()}])

        # MAX / MIN / STD / DESCRIBE
        if op_low in ["max", "min", "std"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                return pd.DataFrame()
            func = getattr(df_filtrado[col_op_real], op_low)
            return pd.DataFrame([{f"{op_low}_{col_op_real}": func()}])
        if op_low == "describe":
            if not col_op_real or col_op_real not in df_filtrado.columns:
                return pd.DataFrame()
            return pd.DataFrame([df_filtrado[col_op_real].describe().to_dict()])

        # TOP / RANKING
        if op_low in ["top", "ranking"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                return df_filtrado
            order = str(entrada.get("ranking", ["desc"])[0]).lower()
            ascending = order in ["asc", "cresc", "ascending"]
            limit = int(entrada.get("limit") or entrada.get("n") or 5)
            cols_show = cols_to_show_mapped if cols_to_show_mapped else df_filtrado.columns.tolist()
            return df_filtrado.sort_values(by=col_op_real, ascending=ascending).head(limit)[cols_show]

        # LIST / LISTAR
        if op_low in ["list", "listar"]:
            cols = cols_to_show_mapped if cols_to_show_mapped else df_filtrado.columns.tolist()
            return df_filtrado[cols]

        # CORRELATION
        if op_low in ["correlacao", "correlation"]:
            corr_cols = entrada.get("correlation") or entrada.get("comparisons") or []
            if isinstance(corr_cols, list) and len(corr_cols) >= 2:
                c1 = mapear_coluna(corr_cols[0], df_map, df, semantico)
                c2 = mapear_coluna(corr_cols[1], df_map, df, semantico)
                if c1 and c2 and c1 in df_filtrado.columns and c2 in df_filtrado.columns:
                    s1 = pd.to_numeric(df_filtrado[c1], errors="coerce")
                    s2 = pd.to_numeric(df_filtrado[c2], errors="coerce")
                    corr_val = s1.corr(s2)
                    return pd.DataFrame([{"correlacao": None if pd.isna(corr_val) else round(float(corr_val), 4), "colunas": f"{c1} vs {c2}"}])
            return pd.DataFrame()

        # COMPARE_MEAN
        if op_low in ["compare_mean", "comparar_media"]:
            comps = entrada.get("comparisons") or []
            if isinstance(comps, list) and len(comps) >= 2:
                col_val = mapear_coluna(comps[0], df_map, df, semantico)
                col_group = mapear_coluna(comps[1], df_map, df, semantico)
                if col_val and col_group and col_val in df_filtrado.columns and col_group in df_filtrado.columns:
                    return df_filtrado.groupby(col_group)[col_val].mean().reset_index(name=f"mean_{col_val}")
            return pd.DataFrame()

        # fallback: operação não reconhecida -> retorna df_filtrado
        return df_filtrado

    except Exception:
        return pd.DataFrame()


# =========================
# Component Langflow
# =========================
class TitanicXLSComponent(Component):
    display_name = "Ferramenta de Pesquisa"
    description = "Componente genérico que processa planilhas Excel via entrada JSON (mapeamento, filtros, operações)."
    icon = "database"
    name = "SearchToolComponent"

    inputs = [
        MessageTextInput(
            name="entrada",
            display_name="Entrada JSON do LLM",
            info="JSON (string ou dict) com instruções: filtros, operações, mapeamento de colunas etc.",
            value="{}",
            tool_mode=True,
        )
    ]
    outputs = [Output(display_name="Output", name="output", method="build_output")]

    def build_output(self) -> Data:
        entrada = self.entrada
        # aceita string JSON ou dict
        if isinstance(entrada, str):
            try:
                entrada = json.loads(entrada)
            except Exception:
                entrada = {}
        if not isinstance(entrada, dict):
            entrada = {}

        # permite sobrescrever arquivo via entrada["arquivo_excel"]
        arquivo_excel = entrada.get("arquivo_excel", "Planilha.xlsx")
        aba = entrada.get("aba", None)
        header_linha = int(entrada.get("header_linha", 0))

        resultado_df = executar_pesquisa(
            entrada=entrada,
            arquivo_excel=arquivo_excel,
            aba=aba,
            header_linha=header_linha,
        )

        # garantir serialização segura para JSON
        resultado_serializavel = to_serializable(resultado_df)

        return Data(value={"resultado": resultado_serializavel})
