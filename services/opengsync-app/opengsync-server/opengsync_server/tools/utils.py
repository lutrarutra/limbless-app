from typing import Optional, Union, TypeVar, Sequence, Callable, get_type_hints, Literal, get_origin, get_args
import difflib
import string
import inspect

import pandas as pd

from opengsync_db import models, exceptions, DBHandler
from .. import logger

from .WeekTimeWindow import WeekTimeWindow

tab_10_colors = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf"
]


def to_identifier(n: int) -> str:
    out = ""

    while n >= 0:
        n, r = divmod(n, 26)
        out = string.ascii_uppercase[r] + out
        n -= 1

    return out


def _hamming_distance_shared_bases(seq1: str, seq2: str) -> int:
    """Calculate Hamming distance using only matching positions (shortest shared length)."""
    min_len = min(len(seq1), len(seq2))
    return sum(c1 != c2 and c1 != 'N' and c2 != 'N' for c1, c2 in zip(seq1[:min_len], seq2[:min_len]))


def min_hamming_distances(seq_list: list[str]) -> list[int]:
    distances = []
    for i, ref in enumerate(seq_list):
        other_seqs = seq_list[:i] + seq_list[i + 1:]
        distances.append(min(_hamming_distance_shared_bases(ref, other) for other in other_seqs))
    return distances


def check_indices(df: pd.DataFrame, groupby: str | None = None) -> pd.DataFrame:
    df["error"] = None
    df["warning"] = None

    indices = ["sequence_i7"]
    if "sequence_i5" in df.columns and not df["sequence_i5"].isna().all():
        indices.append("sequence_i5")

    df["combined_index"] = ""
    if len(df) > 1:
        for index in indices:
            df[index] = df[index].apply(lambda x: x.strip() if pd.notna(x) else "")
            _max = int(df[index].str.len().max())
            df["combined_index"] += df[index].str.ljust(_max, "N")
        
        if "sequence_i5" in df.columns:
            same_barcode_in_different_indices = df["sequence_i7"] == df["sequence_i5"]
            df.loc[same_barcode_in_different_indices, "warning"] = "Same barcode in different indices"
        
        df["min_hamming_bases"] = None
        if groupby is None:
            df["min_hamming_bases"] = min_hamming_distances(df["combined_index"].tolist())
        else:
            for _, _df in df.groupby(groupby):
                if len(_df) < 2:
                    _df["min_hamming_bases"] = _df["combined_index"].apply(lambda x: len(x) - x.count("N"))
                else:
                    _df["min_hamming_bases"] = min_hamming_distances(_df["combined_index"].tolist())
                df.loc[_df.index, "min_hamming_bases"] = _df["min_hamming_bases"]
            
    else:
        df["min_hamming_bases"] = df["combined_index"].apply(lambda x: len(x) - x.count("N"))

    df.loc[df["min_hamming_bases"] < 1, "error"] = "Hamming distance of 0 between barcode combination in two or more libraries."
    df.loc[df["min_hamming_bases"] < 3, "warning"] = "Small hamming distance between barcode combination in two or more libraries."

    return df


def parse_time_windows(s: str) -> list[WeekTimeWindow]:
    from datetime import time
    windows = []
    for entry in s.split(";"):
        weekday, time_range = entry.split("@")
        start_time, end_time = time_range.split("-")
        try:
            weekday = int(weekday)
        except ValueError:
            raise ValueError(f"'{weekday}' is not a valid weekday number (0=Monday,.., 6=Sunday).")
        
        try:
            start_time = time.fromisoformat(start_time)
        except ValueError:
            raise ValueError(f"'{start_time}' is not a valid time in HH:MM format.")
        
        try:
            end_time = time.fromisoformat(end_time)
        except ValueError:
            raise ValueError(f"'{end_time}' is not a valid time in HH:MM format.")
        
        windows.append(WeekTimeWindow(weekday, start_time, end_time))
    return windows


def titlecase_with_acronyms(val: str) -> str:
    return " ".join([c[0].upper() + c[1:] for c in val.split(" ")])


def make_filenameable(val, keep: list[str] = ['-', '.', '_']) -> str:
    return "".join(c for c in str(val) if c.isalnum() or c in keep)


def make_alpha_numeric(val, keep: list[str] = [".", "-", "_"], replace_white_spaces_with: Optional[str] = "_") -> str | None:
    if pd.isna(val) or val is None or val == "":
        return None
    
    if replace_white_spaces_with is not None:
        val = val.strip().replace(" ", replace_white_spaces_with)
    return "".join(c for c in val if c.isalnum() or c in keep)
    

def parse_float(val: Union[int, float, str, None]) -> float | None:
    if isinstance(val, int) or isinstance(val, float):
        return float(val)
    if isinstance(val, str):
        try:
            return float("".join(c for c in val if c.isnumeric() or c == "." or c == "-"))
        except ValueError:
            return None
    return None


def parse_int(val: Union[int, str, None]) -> int | None:
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        try:
            return int("".join(c for c in val if c.isnumeric() or c == "-"))
        except ValueError:
            return None
    return None


T = TypeVar('T')


def mapstr(
    word: str, tuples: list[tuple[str, T]], cutoff: float = 0.5,
    cap_sensitive: bool = False, filter_non_alphanumeric: bool = True,
) -> T | None:
    
    if pd.isna(word):
        return None

    if not cap_sensitive:
        tuples = [(k.lower(), v) for k, v in tuples]

    if filter_non_alphanumeric:
        tuples = [("".join(c for c in k if c.isalnum()), v) for k, v in tuples]

    tuples = [(k.replace(" ", "").replace("_", "").replace("-", ""), v) for k, v in tuples]

    tt = dict(tuples)

    matches = difflib.get_close_matches(word, tt.keys(), n=1, cutoff=cutoff)
    if (match := next(iter(matches), None)) is None:
        return None

    return tt[match]


def connect_similar_strings(
    refs: list[tuple[str, str]], data: list[str],
    similars: Optional[dict[str, str | int]] = None, cutoff: float = 0.5
) -> dict:
    search_dict = dict([(val.lower().replace(" ", "").replace("_", "").replace("-", ""), key) for key, val in refs])

    res = []
    for word in data:
        _word = word.lower().replace(" ", "").replace("_", "").replace("-", "")
        if similars is not None and _word in similars.keys():
            res.append((similars[_word], 1.0))
        else:
            closest_match = difflib.get_close_matches(word, search_dict.keys(), n=1, cutoff=cutoff)
            if len(closest_match) == 0:
                res.append(None)
            else:
                score = difflib.SequenceMatcher(None, word, closest_match[0]).ratio()
                res.append((search_dict[closest_match[0]], score))

    _data = dict(zip(data, res))
    bests = {}
    for key, val in _data.items():
        if val is None:
            continue
        
        if val[0] in bests.keys():
            if val[1] > bests[val[0]][1]:
                bests[val[0]] = (key, val[1])
        else:
            bests[val[0]] = (key, val[1])

    res = {}
    for key, val in _data.items():
        if val is None:
            res[key] = None
            continue

        if val[0] in bests.keys():
            if bests[val[0]][0] == key:
                res[key] = val[0]
            else:
                res[key] = None
    return res


def get_barcode_table(db: DBHandler, libraries: Sequence[models.Library]) -> pd.DataFrame:
    library_data = {
        "library_id": [],
        "library_name": [],
        "library_type_id": [],
        "index_well": [],
        "kit_i7": [],
        "name_i7": [],
        "sequence_i7": [],
        "kit_i5": [],
        "name_i5": [],
        "sequence_i5": [],
    }
    
    for library in libraries:
        if len(library.indices) == 0:
            library_data["library_id"].append(library.id)
            library_data["index_well"].append(None)
            library_data["library_type_id"].append(library.type.id if library.type else None)
            library_data["library_name"].append(library.name)
            library_data["kit_i7"].append(None)
            library_data["name_i7"].append(None)
            library_data["sequence_i7"].append(None)
            library_data["kit_i5"].append(None)
            library_data["name_i5"].append(None)
            library_data["sequence_i5"].append(None)

        else:
            kit_i7s = []
            names_i7 = []
            sequences_i7 = []

            for (kit_i7_id, name_i7), seqs_i7 in library.adapters_i7().items():
                if kit_i7_id is not None:
                    if (kit_i7 := db.get_index_kit(kit_i7_id)) is None:
                        logger.error(f"Index kit {kit_i7_id} not found in database")
                        raise exceptions.ElementDoesNotExist("Index kit not found in database")
                    kit_i7 = kit_i7.identifier
                else:
                    kit_i7 = None
                kit_i7s.append(kit_i7)
                names_i7.append(name_i7)
                sequences_i7.append(";".join(seqs_i7))

            kit_i5s = []
            names_i5 = []
            sequences_i5 = []
            for (kit_i5_id, name_i5), seqs_i5 in library.adapters_i5().items():
                if kit_i5_id is not None:
                    if (kit_i5 := db.get_index_kit(kit_i5_id)) is None:
                        logger.error(f"Index kit {kit_i5_id} not found in database")
                        raise exceptions.ElementDoesNotExist("Index kit not found in database")
                    kit_i5 = kit_i5.identifier
                else:
                    kit_i5 = None
                kit_i5s.append(kit_i5)
                names_i5.append(name_i5)
                sequences_i5.append(";".join(seqs_i5))

            library_data["library_id"].append(library.id)
            library_data["library_name"].append(library.name)
            library_data["index_well"].append(None)
            library_data["library_type_id"].append(library.type.id if library.type else None)
            library_data["kit_i7"].append(";".join(kit_i7s) if len(kit_i7s) else None)
            library_data["name_i7"].append(";".join(names_i7) if len(names_i7) else None)
            library_data["sequence_i7"].append(";".join(sequences_i7) if len(sequences_i7) else None)
            library_data["kit_i5"].append(";".join(kit_i5s) if len(kit_i5s) else None)
            library_data["name_i5"].append(";".join(names_i5) if len(names_i5) else None)
            library_data["sequence_i5"].append(";".join(sequences_i5) if len(sequences_i5) else None)

    df = pd.DataFrame(library_data)
    return df


def get_nameid_column(df: pd.DataFrame, name_col: str, id_col: str, sep: str = "@") -> list[str]:
    return (df[name_col] + sep + df[id_col].astype(str)).tolist()


def parse_nameid_column(df: pd.DataFrame, col: str, sep: str = "@") -> list[int | None]:
    return df[col].apply(lambda x: int(x.split(sep)[-1]) if pd.notna(x) else None).tolist()


def map_columns(dst: pd.DataFrame, src: pd.DataFrame, idx_columns: list[str] | str | None, col: str) -> pd.Series:
    if idx_columns is not None:
        src = src.set_index(idx_columns)

    mapping = src[col].to_dict()
    if isinstance(idx_columns, str):
        return pd.Series(dst[idx_columns].apply(lambda x: mapping.get(x, None) if pd.notna(x) else None))
    return pd.Series(dst[idx_columns].apply(lambda row: mapping.get(tuple(row), None) if isinstance(row, pd.Series) else mapping.get(row), axis=1))


def infer_route(func: Callable) -> str:
    sig = inspect.signature(func)
    hints = get_type_hints(func)

    parts = []
    for name, param in sig.parameters.items():
        if param.default != inspect.Parameter.empty:
            continue
        
        type_hint = hints.get(name, str)
        origin = get_origin(type_hint)
        args = get_args(type_hint)
        
        logger.debug(f"{name=} {type_hint=} {origin=} {args=}")
        
        if type_hint == int:
            converter = "int"
        elif type_hint == str:
            converter = "string"
        elif origin is Literal:
            # You can enforce a type or treat it as string for route
            if all(isinstance(a, str) for a in args):
                converter = "string"
            elif all(isinstance(a, int) for a in args):
                converter = "int"
            else:
                raise ValueError(f"Unsupported Literal types: {args}")
        else:
            raise ValueError(f"Unsupported type hint: {type_hint}")
        
        parts.append(f"<{converter}:{name}>")

    return f"/{func.__name__}/" + "/".join(parts)