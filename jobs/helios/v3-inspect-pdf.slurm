#!/bin/bash -l
#SBATCH --job-name=scout-v3-pdfinfo
#SBATCH --partition=plgrid
#SBATCH --account=plgcredibleai2026-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.out
#SBATCH --error=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.err

set -euo pipefail
: "${SOURCE_ID:?Submit with --export=ALL,SOURCE_ID=<manifest-id>}"

cd "${SLURM_SUBMIT_DIR}"

printf 'gitRevision=%s\n' "$(git rev-parse HEAD)"
printf 'hostname=%s\n' "$(hostname)"
printf 'architecture=%s\n' "$(uname -m)"
printf 'slurmJobId=%s\n' "${SLURM_JOB_ID}"
printf 'partition=%s\n' "${SLURM_JOB_PARTITION}"
printf 'account=%s\n' "${SLURM_JOB_ACCOUNT}"
printf 'sourceId=%s\n' "${SOURCE_ID}"
source_pdf="${SCRATCH}/scouting-autoresearch/sources/${SOURCE_ID}/source.pdf"
inspection_dir="${SCRATCH}/scouting-autoresearch/inspection/${SOURCE_ID}"
pdfinfo_file="${inspection_dir}/pdfinfo.txt"
text_file="${inspection_dir}/pdftotext-layout.txt"
mkdir -p "${inspection_dir}"

module purge
module load GCC/14.3.0 poppler/25.12.0
pdfinfo -v
pdftotext -v
module list
pdfinfo "${source_pdf}" > "${pdfinfo_file}"
pdftotext -layout "${source_pdf}" "${text_file}"

module purge
module load GCCcore/13.3.0 Python/3.12.3
python_venv="${SCRATCH}/scouting-autoresearch/venvs/x86_64-py312-semantic-v3"
source "${python_venv}/bin/activate"
python --version
module list

python scripts/inspect_v3_pdf.py \
  --source-id "${SOURCE_ID}" \
  --pdfinfo-file "${pdfinfo_file}" \
  --text-file "${text_file}"
