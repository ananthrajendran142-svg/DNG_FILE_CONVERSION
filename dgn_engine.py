import sys
import os
import json
import traceback

# Add current directory to path so converter can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from converter import convert_dgn_direct


def main():
    if len(sys.argv) < 3:
        print("DGN Offline Engine v2.0")
        print("Usage: dgn_engine.exe <input_dgn> <output_pdf> [thumb_png] [options_json]")
        sys.exit(1)

    input_path = os.path.abspath(sys.argv[1])
    output_pdf_path = os.path.abspath(sys.argv[2])
    thumb_path = os.path.abspath(sys.argv[3]) if (len(sys.argv) > 3 and sys.argv[3] != "NONE") else None
    
    options = {}
    if len(sys.argv) > 4:
        raw_opts = sys.argv[4].strip()
        if raw_opts:
            try:
                options = json.loads(raw_opts)
            except Exception:
                try:
                    import ast
                    options = ast.literal_eval(raw_opts)
                except Exception as e:
                    print(f"Warning: Failed to parse options: {e}", file=sys.stderr)

    if not os.path.exists(input_path):
        print(f"Error: Input file does not exist: {input_path}", file=sys.stderr)
        sys.exit(2)

    try:
        # Create output directories if needed
        os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
        if thumb_path:
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)

        # Run conversion direct on main thread
        result = convert_dgn_direct(input_path, output_pdf_path, thumb_path, options)
        
        # Write metadata JSON file alongside output PDF for direct VBA offline consumption
        meta_json_path = output_pdf_path + ".meta.json"
        try:
            with open(meta_json_path, "w", encoding="utf-8") as f:
                json.dump(result, f)
        except Exception:
            pass

        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        err_res = {
            'success': False,
            'error': str(e)
        }
        try:
            with open(output_pdf_path + ".meta.json", "w", encoding="utf-8") as f:
                json.dump(err_res, f)
        except Exception:
            pass
        print(json.dumps(err_res))
        sys.exit(1)


if __name__ == '__main__':
    main()
