import pandas as pd
import re
import numpy as np
from typing import Any, Dict, List, Optional

# --- MAPEAMENTO DE TERMOS ---
COLUNAS_MAPEAMENTO = {
    "termo": "Nome Coluna",
    "outro termo": "Outra Coluna",
}
COLUNAS_MAPEAMENTO_LOWER = {k.lower(): v for k, v in COLUNAS_MAPEAMENTO.items()}


# --- Funções auxiliares ---
def normalizar_colunas(df: pd.DataFrame) -> Dict[str, str]:
    mapping = {}
    for col in df.columns:
        mapping[str(col).strip().lower()] = col
    return mapping

def normalizar_coluna_para_busca(df: pd.DataFrame, coluna: str) -> Optional[str]:
    if coluna is None:
        return None
    for col in df.columns:
        if col.lower() == coluna.lower():
            return col
    return None

def mapear_coluna(coluna: Any, df_map: Dict[str, str], df: Optional[pd.DataFrame] = None) -> Optional[str]:
    """Mapeia nomes livres/português para a coluna real do DataFrame.
       Aceita strings e listas (retorna o primeiro elemento útil)."""
    if coluna is None:
        return None
    if isinstance(coluna, list):
        coluna = coluna[0] if coluna else None
    if coluna is None:
        return None
    key = str(coluna).strip().lower()

    # se existir no dicionário semântico
    if key in COLUNAS_MAPEAMENTO_LOWER:
        target = COLUNAS_MAPEAMENTO_LOWER[key]
        if df is not None:
            real = normalizar_coluna_para_busca(df, target)
            if real:
                return real
        return target

    # se corresponde diretamente ao mapeamento de colunas do df
    if key in df_map:
        return df_map[key]

    # busca por substring nas colunas normalizadas
    for k, v in df_map.items():
        if key in k:
            return v

    # tenta achar coluna igual no df (caso user passe nome já real)
    if df is not None:
        col_real = normalizar_coluna_para_busca(df, key)
        if col_real:
            return col_real

    return None

def parse_termos_texto(valor: Any) -> List[str]:
    return [t for t in re.split(r'[\s,;]+', str(valor).strip()) if t]

def detectar_comparacao_numerica(s: Any):
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


# === Função principal ===
def executar_pesquisa(entrada: dict, arquivo_excel: str = "Planilha.xlsx", aba: Optional[int] = None, header_linha: int = 0) -> pd.DataFrame:
    """
    Executa a query definida pela 'entrada' sobre o arquivo Excel.
    Mostra resultados no console e retorna o DataFrame (ou subset) usado.
    """
    try:
        df = pd.read_excel(arquivo_excel, sheet_name=aba or 0, header=header_linha)
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {arquivo_excel}. Verifique o caminho e tente novamente.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Erro ao abrir o arquivo: {e}")
        return pd.DataFrame()

    # limpeza básica de colunas
    df.columns = [str(c).strip() for c in df.columns]
    df_map = normalizar_colunas(df)

    # filtro inicial (todas as linhas)
    filtro = pd.Series(True, index=df.index)

    # --- FILTROS SIMPLES via entrada['data'] ---
    for item in entrada.get("data", []):
        coluna_input = item.get("column_name") or item.get("column")
        valor_input = item.get("value", "")
        coluna_real = mapear_coluna(coluna_input, df_map, df)
        if not coluna_real:
            # sem coluna mapeada, nada a aplicar
            continue

        v = valor_input
        comp = detectar_comparacao_numerica(v)
        if comp:
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

        # texto / termos
        termos = parse_termos_texto(v)
        col_text = df[coluna_real].astype(str).str.lower()
        filtro_termos = pd.Series(False, index=df.index)
        for t in termos:
            filtro_termos |= col_text.str.contains(str(t).lower(), na=False)
        filtro &= filtro_termos

    # --- SPECIAL CONDITIONS (expressões) ---
    specials = entrada.get("special_conditions", []) or []
    if specials:
        # nomes possíveis: colunas reais + chaves do dicionário semântico
        nomes_possiveis = list(df.columns) + list(COLUNAS_MAPEAMENTO_LOWER.keys())
        # padrão que captura palavras (case-insensitive)
        padrao = r"\b(" + "|".join(re.escape(c) for c in nomes_possiveis) + r")\b"
        for cond in specials:
            try:
                cond_str = str(cond)

                def substituir_coluna(match):
                    token = match.group(0)
                    # tenta mapear token (pode ser sinônimo em pt ou nome real)
                    mapped = mapear_coluna(token, df_map, df)
                    # se mapeou, devolve o nome real (preserva case do df)
                    if mapped:
                        return mapped
                    return token

                cond_limpa = re.sub(padrao, substituir_coluna, cond_str, flags=re.IGNORECASE)
                # avalia cond_limpa no contexto do DataFrame
                # usamos try/except para evitar quebra total se expressão inválida
                try:
                    filtro &= df.eval(cond_limpa)
                except Exception as e:
                    print(f"⚠️ Não foi possível avaliar condição '{cond}': expressão convertida '{cond_limpa}'. Erro: {e}")
            except Exception as e:
                print(f"⚠️ Erro ao processar special_condition '{cond}': {e}")

    df_filtrado = df.loc[filtro].copy()

    if df_filtrado.empty:
        print("Nenhum resultado encontrado após aplicar filtros.")
        return df_filtrado

    # --- OPERAÇÕES ---
    col_op = entrada.get("column_operation")
    oper = entrada.get("operation")

    # desfazer listas onde aplicável
    if isinstance(col_op, list):
        col_op = col_op[0] if col_op else None
    if isinstance(oper, list):
        oper = oper[0] if oper else None

    col_op_real = mapear_coluna(col_op, df_map, df) if col_op else None

    # columns_to_show mapeadas
    cols_to_show = entrada.get("columns_to_show") or []
    cols_to_show_mapped = [mapear_coluna(c, df_map, df) for c in cols_to_show] if cols_to_show else []
    cols_to_show_mapped = [c for c in cols_to_show_mapped if c]

    op_low = str(oper).strip().lower() if oper else ""

    try:
        # Se nenhuma operação foi informada: retorna colunas solicitadas (se houver) ou todo df_filtrado
        if not op_low:
            if cols_to_show_mapped:
                print("Nenhuma operação especificada — retornando apenas as colunas solicitadas:")
                print(df_filtrado[cols_to_show_mapped].to_string(index=False))
                return df_filtrado[cols_to_show_mapped]
            else:
                print("Nenhuma operação especificada — retornando DataFrame filtrado completo:")
                print(df_filtrado.to_string(index=False))
                return df_filtrado

        # CONTAGEM (count)
        if op_low in ["count", "contagem"]:
            if col_op_real and col_op_real in df_filtrado.columns:
                total = int(df_filtrado[col_op_real].notna().sum())
                print(f"Contagem de '{col_op_real}': {total}")
            else:
                total = len(df_filtrado)
                print(f"Contagem total de registros: {total}")
            return df_filtrado

        # PORCENTAGEM (percent)
        if op_low in ["porcentagem", "percent", "percentage"]:
            total_geral = len(df)
            total_filtrado = len(df_filtrado)
            # se não há group_by -> porcentagem do total geral
            group_by = entrada.get("group_by", []) or []
            if not group_by:
                pct = (total_filtrado / total_geral) * 100 if total_geral else 0
                print(f"Total geral: {total_geral}")
                print(f"Total filtrado: {total_filtrado}")
                print(f"Porcentagem (do total geral): {pct:.2f}%")
                return df_filtrado
            # se há group_by -> calcular taxa por grupo corretamente (ex: survivors_in_group / total_in_group)
            gb_cols = [mapear_coluna(c, df_map, df) for c in group_by]
            gb_cols = [c for c in gb_cols if c]
            if not gb_cols:
                print("group_by informado, mas não foi possível mapear colunas.")
                return df_filtrado
            # contagens totais por grupo (no df original)
            tot_por_grupo = df.groupby(gb_cols).size().rename("total_no_grupo")
            # contagens filtradas por grupo (após aplicar special_conditions/data)
            filt_por_grupo = df_filtrado.groupby(gb_cols).size().rename("filtrados_no_grupo")
            res = pd.concat([tot_por_grupo, filt_por_grupo], axis=1).fillna(0)
            res["porcentagem_no_grupo"] = (res["filtrados_no_grupo"] / res["total_no_grupo"] * 100).round(2)
            res = res.reset_index()
            print("Porcentagem/taxa por grupo (filtrados / total do grupo):")
            print(res.to_string(index=False))
            return df_filtrado

        # MÉDIA
        if op_low in ["mean", "media"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                print("Coluna para operação 'mean' não encontrada.")
                return df_filtrado
            if entrada.get("group_by"):
                gb = [mapear_coluna(c, df_map, df) for c in entrada.get("group_by")]
                gb = [c for c in gb if c]
                if gb:
                    res = df_filtrado.groupby(gb)[col_op_real].mean().reset_index(name=f"mean_{col_op_real}")
                    print(f"Média de {col_op_real} por {gb}:")
                    print(res.to_string(index=False))
                    return df_filtrado
            mean_val = df_filtrado[col_op_real].dropna().mean()
            print(f"Média ({col_op_real}): {mean_val}")
            return df_filtrado

        # SUM
        if op_low in ["sum", "soma"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                print("Coluna para operação 'sum' não encontrada.")
                return df_filtrado
            total = df_filtrado[col_op_real].dropna().sum()
            print(f"Soma ({col_op_real}): {total}")
            return df_filtrado

        # MAX
        if op_low in ["max"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                print("Coluna para operação 'max' não encontrada.")
                return df_filtrado
            val = df_filtrado[col_op_real].dropna().max()
            print(f"Máximo ({col_op_real}): {val}")
            return df_filtrado

        # MIN
        if op_low in ["min"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                print("Coluna para operação 'min' não encontrada.")
                return df_filtrado
            val = df_filtrado[col_op_real].dropna().min()
            print(f"Mínimo ({col_op_real}): {val}")
            return df_filtrado

        # STD
        if op_low in ["std"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                print("Coluna para operação 'std' não encontrada.")
                return df_filtrado
            val = df_filtrado[col_op_real].dropna().std()
            print(f"Desvio padrão ({col_op_real}): {val}")
            return df_filtrado

        # DESCRIBE
        if op_low in ["describe"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                print("Coluna para operação 'describe' não encontrada.")
                return df_filtrado
            desc = df_filtrado[col_op_real].describe()
            print(f"Describe ({col_op_real}):")
            print(desc.to_string() if hasattr(desc, "to_string") else str(desc))
            return df_filtrado

        # TOP / RANKING
        if op_low in ["top", "ranking"]:
            if not col_op_real or col_op_real not in df_filtrado.columns:
                print("Coluna para operação 'top' não encontrada.")
                return df_filtrado
            order = entrada.get("ranking", [])
            order = str(order[0]).lower() if isinstance(order, list) and order else (str(order).lower() if order else "desc")
            ascending = order in ["asc", "cresc", "ascending"]
            limit = int(entrada.get("limit") or entrada.get("n") or 5)
            cols_show = cols_to_show_mapped if cols_to_show_mapped else df_filtrado.columns.tolist()
            res = df_filtrado.sort_values(by=col_op_real, ascending=ascending).head(limit)
            print(f"Top {limit} por {col_op_real} (ascending={ascending}):")
            print(res[cols_show].to_string(index=False))
            return df_filtrado

        # LISTAR colunas
        if op_low in ["list", "listar"]:
            if cols_to_show_mapped:
                print("Listando colunas solicitadas:")
                print(df_filtrado[cols_to_show_mapped].to_string(index=False))
                return df_filtrado[cols_to_show_mapped]
            else:
                print("Listando todas as colunas do DataFrame filtrado:")
                print(df_filtrado.to_string(index=False))
                return df_filtrado

        # CORRELAÇÃO
        if op_low in ["correlacao", "correlation"]:
            corr_cols = entrada.get("correlation") or entrada.get("comparisons") or []
            if isinstance(corr_cols, list) and len(corr_cols) >= 2:
                c1 = mapear_coluna(corr_cols[0], df_map, df)
                c2 = mapear_coluna(corr_cols[1], df_map, df)
                if c1 in df_filtrado.columns and c2 in df_filtrado.columns:
                    # força numérico quando possível
                    s1 = pd.to_numeric(df_filtrado[c1], errors="coerce")
                    s2 = pd.to_numeric(df_filtrado[c2], errors="coerce")
                    corr_val = s1.corr(s2)
                    print(f"Correlação entre {c1} e {c2}: {corr_val}")
                else:
                    print("Colunas para correlação não encontradas no DataFrame filtrado.")
            else:
                print("Forneça duas colunas para calcular correlação (em 'correlation' ou 'comparisons').")
            return df_filtrado

        # COMPARE_MEAN (média de col_val por col_group)
        if op_low in ["compare_mean", "comparar_media"]:
            comps = entrada.get("comparisons") or []
            if isinstance(comps, list) and len(comps) >= 2:
                col_val = mapear_coluna(comps[0], df_map, df)
                col_group = mapear_coluna(comps[1], df_map, df)
                if col_val and col_group and col_val in df_filtrado.columns and col_group in df_filtrado.columns:
                    res = df_filtrado.groupby(col_group)[col_val].mean().reset_index(name=f"mean_{col_val}")
                    print(f"Média de {col_val} por {col_group}:")
                    print(res.to_string(index=False))
                else:
                    print("Colunas para compare_mean não encontradas.")
            else:
                print("Passe duas colunas em 'comparisons', ex: [\"Fare\", \"Survived\"]")
            return df_filtrado

        # MÉDIA POR GRUPO (quando 'group_by' presente mesmo sem 'operation' específica)
        if entrada.get("group_by") and not op_low:
            gb = [mapear_coluna(c, df_map, df) for c in entrada.get("group_by")]
            gb = [c for c in gb if c]
            if gb:
                if cols_to_show_mapped:
                    print(df_filtrado.groupby(gb)[cols_to_show_mapped].mean().reset_index().to_string(index=False))
                else:
                    print(df_filtrado.groupby(gb).mean().reset_index().to_string(index=False))
            return df_filtrado

        # fallback
        print("Operação não reconhecida.")
        return df_filtrado

    except Exception as e:
        print(f"Erro ao executar operação '{oper}': {e}")
        return df_filtrado


# --- EXEMPLO DE USO ---
if __name__ == "__main__":
    arquivo_excel = "Planilha.xltx"  # ajuste se necessário

    # entrada de exemplo (você pode testar diversas das entradas que listou)
    entrada = {
  "columns_to_show": [],
  "column_operation": [],
  "operation": [],
  "comparisons": [],
  "ranking": [],
  "group_by": [],
  "correlation": [],
  "special_conditions": [],
  "data": [
      {"column_name": "coluna", "value": "valor"}
  ]
}

    executar_pesquisa(entrada, arquivo_excel=arquivo_excel)
