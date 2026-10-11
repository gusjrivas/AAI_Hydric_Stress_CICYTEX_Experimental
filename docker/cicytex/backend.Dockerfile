FROM python:3.11-slim
WORKDIR /workspace
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[backend]"
COPY backend ./backend
COPY results/cicytex/causal_replay ./results/cicytex/causal_replay
ENV PYTHONPATH=/workspace:/workspace/src:/workspace/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV CICYTEX_REPLAY_DIR=/workspace/results/cicytex/causal_replay
WORKDIR /workspace/backend
