#!/bin/bash -l
#SBATCH --job-name=scout-v3-semantic
#SBATCH --partition=plgrid
#SBATCH --account=plgcredibleai2026-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.out
#SBATCH --error=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.err

set -euo pipefail

module purge
module load GCCcore/13.3.0 Python/3.12.3

task_repo="${SLURM_SUBMIT_DIR}"
python_venv="${SCRATCH}/scouting-autoresearch/venvs/x86_64-py312-semantic-v3"
requirements_hash="$(sha256sum "${task_repo}/requirements.txt" | cut -d' ' -f1)"

mkdir -p "$(dirname "${python_venv}")" "${SCRATCH}/scouting-autoresearch/logs"
if [[ ! -x "${python_venv}/bin/python" ]]; then
  python -m venv "${python_venv}"
fi
source "${python_venv}/bin/activate"
if [[ "$(cat "${python_venv}/.requirements.sha256" 2>/dev/null || true)" != "${requirements_hash}" ]]; then
  python -m pip install --disable-pip-version-check -r "${task_repo}/requirements.txt"
  printf '%s\n' "${requirements_hash}" > "${python_venv}/.requirements.sha256"
fi

cd "${task_repo}"
printf 'revision=%s\n' "$(git rev-parse HEAD)"
printf 'hostname=%s architecture=%s\n' "$(hostname)" "$(uname -m)"
printf 'partition=%s account=%s cpus=%s memory=%s\n' \
  "${SLURM_JOB_PARTITION}" "${SLURM_JOB_ACCOUNT}" \
  "${SLURM_CPUS_PER_TASK}" "${SLURM_MEM_PER_NODE}"
python --version
module list

if [[ "${HIERARCHIC_MAP_MODE:-full}" == "smoke" ]]; then
  python -m unittest \
    tests/test_hierarchic_map.py \
    tests/test_semantic_map_hierarchy_publication.py
  python - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / "scripts"))

import numpy as np
from analyze_hierarchic_map import fit_labels

rng = np.random.default_rng(20260909)
features = rng.normal(size=(64, 16))
ids = [f"smoke-{index:03d}" for index in range(64)]
fine, centroids = fit_labels(features, ids, 8, 20260909, 50)
top, _ = fit_labels(centroids, [f"fine-{index:02d}" for index in range(8)], 2, 20260909, 50)
assert len(set(fine)) == 8
assert len(set(top)) == 2
print("hierarchic-map-smoke=passed points=64 fine=8 top=2")
PY
  python scripts/render_semantic_map.py --smoke \
    --output "${SCRATCH}/scouting-autoresearch/hierarchic-map-pilot"
  printf 'status=smoke-passed\n'
  exit 0
fi
if [[ "${HIERARCHIC_MAP_MODE:-full}" == "preapproval" ]]; then
  python -m unittest discover -s tests -p 'test_*.py'
  python scripts/validate.py
  printf 'status=preapproval-passed\n'
  exit 0
fi
python scripts/audit_v3_participants.py
python scripts/audit_v3_facets.py
python scripts/analyze_semantic_map.py --check
python scripts/analyze_hierarchic_map.py --check
python scripts/build_content.py
python scripts/render_semantic_map.py
python scripts/build_semantic_review_packet.py
python scripts/analyze_duplicates.py
python -m unittest discover -s tests -p 'test_*.py'
python scripts/analyze_semantic_map.py --check
python scripts/render_semantic_map.py --check
python scripts/build_semantic_review_packet.py --check
python scripts/analyze_duplicates.py --check
python scripts/validate.py

printf 'status=passed\n'
