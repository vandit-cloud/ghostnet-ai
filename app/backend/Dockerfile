FROM python:3.11-slim

WORKDIR /app

# libgl1/libglib2.0-0/libsm6/libxext6/libxrender1/libxcb1: ultralytics
# installs opencv-python alongside opencv-python-headless as one of ITS OWN
# dependencies (it does not accept headless as a substitute), and whichever
# copy of cv2 lands on disk last wins -- so this image ends up needing the
# GUI build's runtime libraries even though headless is what the rest of the
# code actually imports. Missing them fails as
# "ImportError: libxcb.so.1: cannot open shared object file" the first time
# anything imports ultralytics (i.e. the first real detection job).
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The AI half lives at the repository root (ai/) -- see
# app/services/ghostnet_adapter.py for the full story. Installed editable with
# --no-deps because ai/pyproject.toml also lists torch, torchvision and
# ultralytics with loose version bounds; those are installed explicitly below
# instead so the CPU-only wheel is picked deliberately rather than whatever
# pip would otherwise resolve.
#
# CPU-only torch/ultralytics ARE installed here (unlike an earlier version of
# this file, which left them out to save ~1 GB and ran on MockAIAdapter's fake
# detections instead). Real detection needs the promoted checkpoint at
# ai/models/trained/ghostnet.pt to actually load, and it can't without these.
# No GPU in this container -- ghostnet.config.resolve_device() falls back to
# CPU by design, just slower.
#
# numpy/pyproj/opencv are also installed explicitly for the same reason
# ai/requirements.txt's exact pins (numpy==2.5.1 etc) target the dev's Python
# 3.12 machine and won't resolve on this image's 3.11 -- ai/pyproject.toml's
# own loose bounds are what a consumer environment is meant to use instead.
COPY ai ./ai
RUN pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        torch==2.13.0 torchvision==0.28.0 \
    && pip install --no-cache-dir \
        "numpy>=1.26" "pyproj>=3.6" "opencv-python-headless>=4.10" "ultralytics>=8.3" \
    && pip install --no-cache-dir -e ./ai --no-deps

COPY app/backend/ .

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
