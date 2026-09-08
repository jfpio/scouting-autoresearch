#!/bin/bash -l
#SBATCH --job-name=scout-v3-fetch
#SBATCH --partition=plgrid
#SBATCH --account=plgcredibleai2026-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=02:00:00
#SBATCH --output=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.out
#SBATCH --error=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.err

set -euo pipefail

: "${SOURCE_ID:?Submit with --export=ALL,SOURCE_ID=<manifest-id>}"
LIMIT="${LIMIT:-}"

module purge
module load GCCcore/13.3.0 Python/3.12.3

python_venv="${SCRATCH}/scouting-autoresearch/venvs/x86_64-py312-semantic-v3"
if [[ ! -x "${python_venv}/bin/python" ]]; then
  printf 'Missing x86_64 Python environment: %s\n' "${python_venv}" >&2
  exit 1
fi
source "${python_venv}/bin/activate"
cd "${SLURM_SUBMIT_DIR}"

printf 'gitRevision=%s\n' "$(git rev-parse HEAD)"
printf 'hostname=%s\n' "$(hostname)"
printf 'architecture=%s\n' "$(uname -m)"
printf 'slurmJobId=%s\n' "${SLURM_JOB_ID}"
printf 'partition=%s\n' "${SLURM_JOB_PARTITION}"
printf 'account=%s\n' "${SLURM_JOB_ACCOUNT}"
printf 'sourceId=%s\n' "${SOURCE_ID}"
python --version
module list

command=(python scripts/acquire_v3_sources.py --source-id "${SOURCE_ID}" --execute)
if [[ -n "${LIMIT}" ]]; then
  command+=(--limit "${LIMIT}")
fi
"${command[@]}"
