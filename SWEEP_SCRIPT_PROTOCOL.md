# Sweep Script Protocol — For LLM Code Generation

This document describes the conventions and requirements for writing bash
sweep scripts that are compatible with the Sweep Dashboard dispatch system
and the `run_with_autoresume.sh` training infrastructure.

## Overview

Sweep scripts are self-contained bash scripts that run one or more RL
training experiments sequentially or in parallel (across GPUs). They are
dispatched to remote compute nodes via the Sweep Dashboard, which:

1. Copies the script to `<work_dir>/dispatched_scripts/` on the target node
2. Launches it via `screen -dmS <name> bash -c '...'` (or `nohup`)
3. Captures stdout/stderr to a `.log` file alongside the script

## Required Script Structure

Every sweep script MUST follow this template:

    #!/usr/bin/env bash
    set -euo pipefail

    # ============================================================
    # <Sweep Name>: <Brief Description>
    # ============================================================
    #
    # <Detailed description of what this sweep tests>
    #
    # Conditions:
    #   <condition_1>: <description>
    #   <condition_2>: <description>
    #
    # Schedule: <describe GPU pairing and sequencing>
    #
    # Usage:
    #   nohup bash <script_name>.sh > <log_name>.log 2>&1 &
    #
    # ============================================================

    # --- CONFIGURABLE PATHS (set by dashboard or manually) ---
    # The dashboard may override WORK_DIR via environment variable.
    WORK_DIR="${WORK_DIR:-/home/talmolab/Desktop/SalkResearch/vnl-playground}"
    VENV_PATH="${VENV_PATH:-/home/talmolab/Desktop/SalkResearch/mimic-mjx/bin/activate}"

    cd "$WORK_DIR"

    # Kill all child processes on exit
    trap 'echo "Caught signal — killing children..."; kill 0; wait 2>/dev/null; echo "Cleanup done."; exit 1' INT TERM HUP

    # Activate virtual environment
    source "$VENV_PATH"

    # --- SWEEP CONFIGURATION ---
    BASE_CONFIG="rodent_run_gap/vision_task_obs_transfer"  # Hydra config name
    GROUP="sweep-<name>"                                    # WandB group name
    TIMESTEPS=500000000                                     # Steps per run

    COMMON_OVERRIDES=(
        "--config-name=${BASE_CONFIG}"
        "train_setup.train_config.num_timesteps=${TIMESTEPS}"
        "logging_config.group_name=${GROUP}"
    )

    # --- HELPER FUNCTIONS ---
    # (see below)

    # --- RUN EXPERIMENTS ---
    # (see below)

## Key Conventions

### Environment Variables

The dashboard sets these environment variables before launching:

| Variable | Purpose | Example |
|----------|---------|---------|
| `WORK_DIR` | Working directory on the node | `/root/SalkResearch/vnl-playground` |
| `VENV_PATH` | Path to venv activate script | `/root/SalkResearch/mimic-mjx/bin/activate` |
| `CUDA_VISIBLE_DEVICES` | GPU(s) to use (if set by user in dispatch form) | `0` or `0,1` |
| `JOB_TAG` | Unique tag for autoresume state files | `p1a_w0` |

**IMPORTANT:** Always use `${WORK_DIR:-<default>}` and `${VENV_PATH:-<default>}`
so the script works both when dispatched by the dashboard AND when run manually.

### Training Launch Command

Always use the autoresume wrapper, never call `python -m` directly:

    CUDA_VISIBLE_DEVICES=<gpu> JOB_TAG=<tag> \
        ./vnl_playground/run_with_autoresume.sh \
        "${COMMON_OVERRIDES[@]}" \
        "logging_config.exp_name=<experiment_name>" \
        "<override.path>=<value>"

### GPU Scheduling Patterns

**Single GPU run:**

    run_solo() {
        local tag="$1" exp="$2" gpu="${3:-0}"

        cleanup_state "$tag"

        CUDA_VISIBLE_DEVICES=$gpu JOB_TAG="${tag}" \
            ./vnl_playground/run_with_autoresume.sh \
            "${COMMON_OVERRIDES[@]}" \
            "logging_config.exp_name=${exp}" \
            # ... experiment-specific overrides

        cleanup_state "$tag"
    }

**Parallel pair (2 GPUs):**

    run_pair() {
        local tag0="$1" exp0="$2" <params0...>
        local tag1="$3" exp1="$4" <params1...>

        cleanup_state "$tag0"
        cleanup_state "$tag1"

        CUDA_VISIBLE_DEVICES=0 JOB_TAG="${tag0}" \
            ./vnl_playground/run_with_autoresume.sh \
            "${COMMON_OVERRIDES[@]}" \
            "logging_config.exp_name=${exp0}" \
            <overrides0> &
        local pid0=$!

        sleep 5  # Stagger to avoid timestamp collisions

        CUDA_VISIBLE_DEVICES=1 JOB_TAG="${tag1}" \
            ./vnl_playground/run_with_autoresume.sh \
            "${COMMON_OVERRIDES[@]}" \
            "logging_config.exp_name=${exp1}" \
            <overrides1> &
        local pid1=$!

        wait $pid0 $pid1

        cleanup_state "$tag0"
        cleanup_state "$tag1"
    }

### Autoresume State Cleanup

Always clean up state files before and after each run:

    cleanup_state() {
        local tag="$1"
        rm -f "${WORK_DIR}/.autoresume_state_${tag}"
    }

### Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Script filename | `sweep_<phase>_<parameter>.sh` | `sweep_p1a_termpenalty.sh` |
| WandB group | `sweep-<phase>-<parameter>` | `sweep-p1a-termpenalty` |
| Experiment name | `<parameter>_<value>` | `termpenalty_w5` |
| JOB_TAG | `<phase>_<short_id>` | `p1a_w5` |

### Hydra Override Syntax

Hydra overrides are passed as positional arguments after `--config-name`:

    # Set a value:
    "env_config.env_args.reward_terms.termination_penalty.weight=5.0"

    # Nested path:
    "train_setup.train_config.num_envs=1024"

    # String value (quote inner value):
    "logging_config.exp_name=my_experiment"

    # Resume from checkpoint (+ prefix for new key):
    "+train_setup.resume_run_id='abc123'"

### Logging and Output

- The autoresume wrapper logs each attempt to `training_attempt_<N>_<tag>.log`
- The dispatch system captures overall script output to `<screen_name>.log`
- Always include echo statements for progress tracking:

      echo "============================================================"
      echo "  <Sweep Name>"
      echo "  Started: $(date)"
      echo "============================================================"

### Error Handling

- Use `set -euo pipefail` at the top of every script
- Use the trap pattern to kill child processes on signal
- The autoresume wrapper handles individual training crashes (up to 50 retries)
- The sweep script handles sequencing across experiments

## Config Files Available

Base configs live in `vnl_playground/config/rodent_run_gap/`:

| Config | Architecture | Description |
|--------|-------------|-------------|
| `vision_task_obs_transfer` | MLP + monocular CNN | Standard vision + task obs |
| `task_obs_transfer` | MLP only | No vision (baseline) |
| `shared_vision_task_obs_transfer` | Shared CNN | Shared visual encoder |
| `recurrent_vision_task_obs_transfer` | Recurrent | GRU + vision |
| `binocular_vision_task_obs_transfer` | Binocular CNN | Stereo vision |

## Common Override Paths

| Path | Type | Description |
|------|------|-------------|
| `train_setup.train_config.num_timesteps` | int | Total training steps |
| `train_setup.train_config.num_envs` | int | Parallel environments |
| `logging_config.group_name` | str | WandB group |
| `logging_config.exp_name` | str | WandB experiment name |
| `env_config.env_args.reward_terms.<term>.weight` | float | Reward term weight |
| `env_config.env_args.termination_config.min_torso_z` | float | Min torso height |
| `env_config.env_args.termination_config.max_torso_angle` | float | Max torso angle (deg) |
| `network_config.cnn_channels` | list[int] | CNN channel dims |
| `network_config.hidden_layer_sizes` | list[int] | MLP hidden sizes |
| `render_config.render_every` | int | Render frequency (steps) |

## Complete Example

    #!/usr/bin/env bash
    set -euo pipefail

    # ============================================================
    # Phase 2a: Learning Rate Sweep
    # ============================================================
    # Tests how learning rate affects convergence with vision encoder.
    #
    # Conditions:
    #   lr3e4: learning_rate=3e-4 (default)
    #   lr1e4: learning_rate=1e-4
    #   lr1e3: learning_rate=1e-3
    #   lr5e5: learning_rate=5e-5
    #
    # Schedule (2 GPUs, 500M steps):
    #   Pair 1: lr3e4 (GPU0) + lr1e4 (GPU1)
    #   Pair 2: lr1e3 (GPU0) + lr5e5 (GPU1)
    # ============================================================

    WORK_DIR="${WORK_DIR:-/home/talmolab/Desktop/SalkResearch/vnl-playground}"
    VENV_PATH="${VENV_PATH:-/home/talmolab/Desktop/SalkResearch/mimic-mjx/bin/activate}"
    cd "$WORK_DIR"

    trap 'echo ""; echo "Caught signal — killing all children..."; kill 0; wait 2>/dev/null; echo "Cleanup done."; exit 1' INT TERM HUP

    source "$VENV_PATH"

    BASE_CONFIG="rodent_run_gap/vision_task_obs_transfer"
    GROUP="sweep-p2a-learningrate"
    TIMESTEPS=500000000

    COMMON_OVERRIDES=(
        "--config-name=${BASE_CONFIG}"
        "train_setup.train_config.num_timesteps=${TIMESTEPS}"
        "logging_config.group_name=${GROUP}"
    )

    echo "============================================================"
    echo "  Phase 2a: Learning Rate Sweep"
    echo "  Base config: ${BASE_CONFIG}"
    echo "  Timesteps: ${TIMESTEPS}"
    echo "  Group: ${GROUP}"
    echo "  Started: $(date)"
    echo "============================================================"

    cleanup_state() {
        local tag="$1"
        rm -f "${WORK_DIR}/.autoresume_state_${tag}"
    }

    run_pair() {
        local tag0="$1" exp0="$2" lr0="$3"
        local tag1="$4" exp1="$5" lr1="$6"

        echo "--- Pair: ${exp0} (GPU0) + ${exp1} (GPU1) | $(date) ---"
        cleanup_state "$tag0"; cleanup_state "$tag1"

        CUDA_VISIBLE_DEVICES=0 JOB_TAG="${tag0}" \
            ./vnl_playground/run_with_autoresume.sh \
            "${COMMON_OVERRIDES[@]}" \
            "logging_config.exp_name=${exp0}" \
            "train_setup.train_config.learning_rate=${lr0}" &
        local pid0=$!; sleep 5

        CUDA_VISIBLE_DEVICES=1 JOB_TAG="${tag1}" \
            ./vnl_playground/run_with_autoresume.sh \
            "${COMMON_OVERRIDES[@]}" \
            "logging_config.exp_name=${exp1}" \
            "train_setup.train_config.learning_rate=${lr1}" &
        local pid1=$!

        echo "  PIDs: GPU0=${pid0} GPU1=${pid1}"
        wait $pid0 $pid1
        cleanup_state "$tag0"; cleanup_state "$tag1"
        echo "  Pair done: $(date)"
    }

    # Pair 1: default + lower
    run_pair "p2a_lr3e4" "lr_3e-4" "3e-4" \
             "p2a_lr1e4" "lr_1e-4" "1e-4"

    # Pair 2: higher + lowest
    run_pair "p2a_lr1e3" "lr_1e-3" "1e-3" \
             "p2a_lr5e5" "lr_5e-5" "5e-5"

    echo "============================================================"
    echo "  Phase 2a COMPLETE — $(date)"
    echo "============================================================"
