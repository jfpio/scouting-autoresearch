#!/bin/bash -l
#SBATCH --job-name=scout-v3-contact
#SBATCH --partition=plgrid
#SBATCH --account=plgcredibleai2026-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
#SBATCH --output=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.out
#SBATCH --error=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.err

set -euo pipefail

: "${SOURCE_ID:?Submit with --export=ALL,SOURCE_ID=<manifest-id>}"
if [[ ! "${SOURCE_ID}" =~ ^[a-z0-9][a-z0-9-]+$ ]]; then
  printf 'Unsafe source ID: %s\n' "${SOURCE_ID}" >&2
  exit 2
fi

repo="${SLURM_SUBMIT_DIR}"
source_dir="${repo}/artifacts/sources/${SOURCE_ID}/views"
checkpoint="${repo}/data/checkpoints/source-acquisition/${SOURCE_ID}.json"
inspection_checkpoint="${repo}/data/checkpoints/source-inspection/${SOURCE_ID}.json"
run_root="${SCRATCH}/scouting-autoresearch/runs/${SOURCE_ID}"
result_dir="${run_root}/contact-sheet/${SLURM_JOB_ID}"

if [[ ! -s "${checkpoint}" ]]; then
  printf 'Missing acquisition checkpoint: %s\n' "${checkpoint}" >&2
  exit 3
fi
status="$(jq -r '.status' "${checkpoint}")"
expected="$(jq -r '.expectedImageCount // empty' "${checkpoint}")"
if [[ "${status}" == "complete" && ! "${expected}" =~ ^[1-9][0-9]*$ && -s "${inspection_checkpoint}" ]]; then
  inspection_status="$(jq -r '.status' "${inspection_checkpoint}")"
  inspection_classification="$(jq -r '.classification' "${inspection_checkpoint}")"
  if [[ "${inspection_status}" == "complete" && "${inspection_classification}" == "image-ocr-required" ]]; then
    expected="$(jq -r '.pdf.pages // empty' "${inspection_checkpoint}")"
  fi
fi
if [[ "${status}" != "complete" || ! "${expected}" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Acquisition is not complete: status=%s expected=%s\n' "${status}" "${expected}" >&2
  exit 4
fi

mapfile -t page_images < <(find "${source_dir}" -maxdepth 1 -type f -name 'view-*' -print | sort -V)
if [[ "${#page_images[@]}" -ne "${expected}" ]]; then
  printf 'Expected %s images, found %s\n' "${expected}" "${#page_images[@]}" >&2
  exit 5
fi

mkdir -p "${run_root}"
temporary_dir="$(mktemp -d "${run_root}/thumbnails.XXXXXX")"
cleanup() {
  if [[ -n "${temporary_dir:-}" && "${temporary_dir}" == "${run_root}/thumbnails."* ]]; then
    rm -rf -- "${temporary_dir}"
  fi
}
trap cleanup EXIT

module purge
module load GCC/14.3.0 ImageMagick/7.1.2-7
mkdir -p "${result_dir}"

printf 'gitRevision=%s\n' "$(git -C "${repo}" rev-parse HEAD)"
printf 'hostname=%s\n' "$(hostname)"
printf 'architecture=%s\n' "$(uname -m)"
printf 'sourceId=%s\n' "${SOURCE_ID}"
printf 'expectedImages=%s\n' "${expected}"
module list
magick -version

for page_image in "${page_images[@]}"; do
  page_name="$(basename "${page_image}")"
  magick "${page_image}" -thumbnail '220x285>' "${temporary_dir}/${page_name}"
done
mapfile -t thumbnails < <(find "${temporary_dir}" -maxdepth 1 -type f -name 'view-*' -print | sort -V)
if [[ "${#thumbnails[@]}" -ne "${expected}" ]]; then
  printf 'Expected %s thumbnails, found %s\n' "${expected}" "${#thumbnails[@]}" >&2
  exit 6
fi

magick montage \
  "${thumbnails[@]}" \
  -set label '%t' \
  -pointsize 12 \
  -tile 10x \
  -geometry '220x285+4+16>' \
  -background white \
  "${result_dir}/contact-sheet-view-order.jpg"

identify "${result_dir}/contact-sheet-view-order.jpg"
sha256sum "${result_dir}/contact-sheet-view-order.jpg"
printf 'renderedImages=%s\n' "${#thumbnails[@]}"
printf 'resultDirectory=%s\n' "${result_dir}"
