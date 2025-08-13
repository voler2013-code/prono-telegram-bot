import io
import sys
from contextlib import redirect_stdout
import prono_termico3

def resolver_consulta(texto: str) -> str:
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            prono_termico3.procesar_consulta(texto)
    except SystemExit:
        pass
    output = buf.getvalue().strip()
    buf.close()
    if not output:
        return "No se generó salida para la consulta."
    return output
