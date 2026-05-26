import json
from pathlib import Path

from langchain_core.tools import tool


@tool
def write_excel(data: str, output_path: str, sheet_name: str = "Release Note") -> str:
    """将 JSON 数据写入 Excel 文件。data 为 JSON 字符串，格式为 {"columns": ["列1", "列2"], "rows": [["值1", "值2"], ...]}。"""
    try:
        from openpyxl import Workbook

        parsed = json.loads(data)
        columns = parsed.get("columns", [])
        rows = parsed.get("rows", [])

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name

        # Write header
        for col_idx, col_name in enumerate(columns, start=1):
            ws.cell(row=1, column=col_idx, value=col_name)

        # Write data rows
        for row_idx, row_data in enumerate(rows, start=2):
            for col_idx, value in enumerate(row_data, start=1):
                ws.cell(row=row_idx, column=col_idx, value=str(value) if value is not None else "")

        # Auto-adjust column widths
        for col_idx, col_name in enumerate(columns, start=1):
            max_len = len(str(col_name))
            for row in rows:
                if col_idx - 1 < len(row) and row[col_idx - 1]:
                    max_len = max(max_len, len(str(row[col_idx - 1])))
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 2, 60)

        # Resolve output path
        path = Path(output_path)
        if not path.is_absolute():
            from config import PROJECT_ROOT
            path = PROJECT_ROOT / path

        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(path))
        return f"成功写入 Excel: {path} ({len(rows)} 行)"

    except ImportError:
        return "错误: openpyxl 未安装，请运行 pip install openpyxl"
    except json.JSONDecodeError as exc:
        return f"错误: JSON 解析失败 - {exc}"
    except Exception as exc:
        return f"错误: 写入 Excel 失败 - {exc}"


@tool
def read_excel(input_path: str, sheet_name: str = "Release Note") -> str:
    """读取已有 Excel 文件，返回 JSON 格式数据。格式为 {"columns": ["列1", "列2"], "rows": [["值1", "值2"], ...]}。"""
    try:
        from openpyxl import load_workbook

        path = Path(input_path)
        if not path.is_absolute():
            from config import PROJECT_ROOT
            path = PROJECT_ROOT / path

        if not path.exists():
            return json.dumps({"columns": [], "rows": []}, ensure_ascii=False)

        wb = load_workbook(str(path), read_only=True)
        if sheet_name not in wb.sheetnames:
            wb.close()
            return json.dumps({"columns": [], "rows": []}, ensure_ascii=False)

        ws = wb[sheet_name]
        rows_iter = ws.iter_rows(values_only=True)

        # First row is header
        header_row = next(rows_iter, None)
        if header_row is None:
            wb.close()
            return json.dumps({"columns": [], "rows": []}, ensure_ascii=False)

        columns = [str(c) if c is not None else "" for c in header_row]
        rows = []
        for row in rows_iter:
            rows.append([str(c) if c is not None else "" for c in row])

        wb.close()
        return json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False)

    except ImportError:
        return "错误: openpyxl 未安装，请运行 pip install openpyxl"
    except Exception as exc:
        return f"错误: 读取 Excel 失败 - {exc}"


EXCEL_TOOLS = [write_excel, read_excel]
