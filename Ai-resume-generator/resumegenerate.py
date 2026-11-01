import os
import time


def _configure_weasyprint_dlls():
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return

    gtk_paths = [
        r"C:\Program Files\GTK3-Runtime Win64\bin",
        r"C:\Program Files\GTK4-Runtime Win64\bin",
        r"C:\msys64\ucrt64\bin",
        r"C:\msys64\mingw64\bin",
    ]
    for path in gtk_paths:
        if os.path.isdir(path):
            os.add_dll_directory(path)


def generate_resume_pdf(html_content, base_url=None):
    try:
        _configure_weasyprint_dlls()
        from weasyprint import HTML
    except Exception as exc:
        raise RuntimeError(
            "PDF export is unavailable. Install WeasyPrint and the Windows GTK runtime, then retry."
        ) from exc

    os.makedirs("resumes", exist_ok=True)
    filename = f"Resume_{int(time.time())}.pdf"
    path = os.path.join("resumes", filename)

    HTML(string=html_content, base_url=base_url).write_pdf(path)
    return path
