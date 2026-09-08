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

python scripts/audit_v3_participants.py
python scripts/audit_v3_facets.py
python scripts/analyze_semantic_map.py
python scripts/build_content.py
python scripts/build_semantic_review_packet.py
python scripts/analyze_duplicates.py
python -m unittest discover -s tests -p 'test_*.py'
python scripts/analyze_semantic_map.py --check
python scripts/build_semantic_review_packet.py --check
python scripts/analyze_duplicates.py --check
python scripts/validate.py

printf 'status=passed\n'
