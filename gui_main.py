"""Jarvis — Point d'entrée GUI."""

import os
import sys

# Pre-import torch BEFORE PyQt6 — importing torch for the first time
# inside a QThread causes a segfault (CUDA DLL init + Qt conflict).
# See: pytorch/pytorch#11326, pytorch/pytorch#166628
os.environ["CUDA_MODULE_LOADING"] = "LAZY"
import torch  # noqa: E402

if torch.cuda.is_available():
    torch.cuda.init()

from jarvis.gui.app import JarvisApp  # noqa: E402

if __name__ == "__main__":
    app = JarvisApp(sys.argv)
    sys.exit(app.exec())
