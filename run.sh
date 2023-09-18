#!/bin/bash
#SBATCH --partition=tinyq
#SBATCH --qos=tinyq
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time 02:00:00
#SBATCH --job-name dev
#SBATCH --output /nobackup/lab_bsf/users/agynter/logs/%j.log

# get tunneling info
port=$(shuf -i8000-9999 -n1)
node=$(hostname).int.cemm.at
user=$(whoami)

host ${node}

echo "http://${node}:${port}"

echo "scancel --user=agynter ${SLURM_JOB_ID}"

LOG="/nobackup/lab_bsf/users/agynter/logs/$SLURM_JOB_ID.log"
LATEST_LOG_SYMLINK="/home/agynter/documents/logs/limbless.log"
rm -f "$LATEST_LOG_SYMLINK"
ln -s "$LOG" "$LATEST_LOG_SYMLINK"

# load modules here
# module load JupyterLab-extensions/3.4.3-foss-2022a
source /home/agynter/.bashrc
conda activate dev

# DON'T USE ADDRESS BELOW.
# DO USE TOKEN BELOW
export EMAIL_USER=${EMAIL_USER}
export EMAIL_PASS=${EMAIL_PASS}
python /home/agynter/documents/limbless/run.py --debug --port=${port} --host=0.0.0.0