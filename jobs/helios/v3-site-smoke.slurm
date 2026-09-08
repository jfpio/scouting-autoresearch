#!/bin/bash -l
#SBATCH --job-name=scout-v3-site
#SBATCH --partition=plgrid
#SBATCH --account=plgcredibleai2026-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/v3-site-smoke-%j.out
#SBATCH --error=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/v3-site-smoke-%j.err

set -euo pipefail

module purge
module load GCCcore/13.3.0 Python/3.12.3

task_repo="${SLURM_SUBMIT_DIR}"
npm_cache="${SCRATCH}/scouting-autoresearch/npm-cache"
python_venv="${SCRATCH}/scouting-autoresearch/venvs/x86_64-py312"
nvm_root="${SCRATCH}/scouting-autoresearch/nvm-x86_64"
node_version="22.19.0"
work_dir="${SCRATCH}/scouting-autoresearch/web/x86_64-node22"
lock_hash_file="${work_dir}/.package-lock.sha256"
dependency_cache="${SCRATCH}/scouting-autoresearch/web/node22-dependency-cache"
dependency_archive="${dependency_cache}/node_modules.tar.gz"
dependency_hash_file="${dependency_cache}/package-lock.sha256"

mkdir -p "${work_dir}" "${npm_cache}" "${nvm_root}" "${dependency_cache}"

remove_generated_tree() {
  local target="$1"
  if [[ -d "${target}" && "${target}" == "${work_dir}/"* ]]; then
    find "${target}" -xdev -depth -delete
  fi
}

cleanup() {
  remove_generated_tree "${work_dir}/artifacts"
  remove_generated_tree "${work_dir}/data/embeddings"
  remove_generated_tree "${work_dir}/vault"
  remove_generated_tree "${work_dir}/node_modules"
  remove_generated_tree "${work_dir}/dist"
  remove_generated_tree "${work_dir}/.astro"
}
trap cleanup EXIT

if [[ "$(git -C "${task_repo}" branch --show-current)" != "codex/autoresearch-2026-09-06-v3-sources" ]]; then
  printf 'Unexpected branch: %s\n' "$(git -C "${task_repo}" branch --show-current)" >&2
  exit 2
fi
if [[ ! -x "${python_venv}/bin/python" ]]; then
  printf 'Missing x86_64 Python environment: %s\n' "${python_venv}" >&2
  exit 3
fi

source "${python_venv}/bin/activate"
node_bin="${nvm_root}/versions/node/v${node_version}/bin"
if [[ ! -x "${node_bin}/node" ]]; then
  export NVM_DIR="${nvm_root}"
  source "${HOME}/.nvm/nvm.sh"
  nvm install "${node_version}"
fi
export PATH="${node_bin}:${PATH}"
if [[ "$(node --version)" != "v${node_version}" ]]; then
  printf 'Unexpected Node version: %s\n' "$(node --version)" >&2
  exit 4
fi

hostname
uname -m
module list
python --version
node --version
npm --version
printf 'revision=%s\n' "$(git -C "${task_repo}" rev-parse HEAD)"
printf 'partition=%s account=%s cpus=%s memory=%s\n' \
  "${SLURM_JOB_PARTITION}" "${SLURM_JOB_ACCOUNT}" \
  "${SLURM_CPUS_PER_TASK}" "${SLURM_MEM_PER_NODE}"

# Generated source files belong to the working branch; binary build artifacts do not.
python "${task_repo}/scripts/build_content.py"
remove_generated_tree "${work_dir}/artifacts"
remove_generated_tree "${work_dir}/data/embeddings"
remove_generated_tree "${work_dir}/vault"
rsync -a --delete \
  --exclude='.package-lock.sha256' \
  --exclude='.git/' \
  --exclude='artifacts/' \
  --exclude='data/embeddings/' \
  --exclude='vault/' \
  --exclude='.astro/' \
  --exclude='dist/' \
  --exclude='node_modules/' \
  "${task_repo}/" "${work_dir}/"

cd "${work_dir}"
current_lock_hash="$(sha256sum package-lock.json | cut -d' ' -f1)"
stored_lock_hash="$(cat "${lock_hash_file}" 2>/dev/null || true)"
cached_lock_hash="$(cat "${dependency_hash_file}" 2>/dev/null || true)"
if [[ ! -d node_modules && -f "${dependency_archive}" && "${cached_lock_hash}" == "${current_lock_hash}" ]]; then
  tar -xzf "${dependency_archive}"
elif [[ ! -d node_modules || "${stored_lock_hash}" != "${current_lock_hash}" ]]; then
  npm ci --cache "${npm_cache}" --no-audit --no-fund
  printf '%s\n' "${current_lock_hash}" > "${lock_hash_file}"
fi
if [[ ! -f "${dependency_archive}" || "${cached_lock_hash}" != "${current_lock_hash}" ]]; then
  archive_tmp="${dependency_archive}.job-${SLURM_JOB_ID}"
  tar -czf "${archive_tmp}" node_modules
  mv -f "${archive_tmp}" "${dependency_archive}"
  printf '%s\n' "${current_lock_hash}" > "${dependency_hash_file}"
fi
npm run build
python scripts/check_links.py
python "${task_repo}/scripts/validate.py"

printf 'status=passed\n'
