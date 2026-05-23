# Model Checkpoints - 2026-05-22

This document records the current public model checkpoints for the CARLA
self-driving seminar project.

## Current Recommended Model

- `models/final_carla_imitation_all_cuda.pt`
- Initialized from: `models/stopSignHard_v2_blend_cuda.pt`
- Dataset list: `logs/carla_imitation_all_available_weighted_datasets.txt`
- Device: CUDA
- Epochs: `2`
- Batch size: `512`
- DataLoader workers: `6`
- Learning rate: `0.000005`
- Samples: `16,224,353`
- Train loss: `0.007642932119181981`
- Validation loss: `0.00737966807321996`

Training command:

```bat
set LEARNING_RATE=0.000005&& set EPOCHS=2&& set BATCH_SIZE=512&& set NUM_WORKERS=6&& scripts\train_tar_shards_fast_windows.bat logs\carla_imitation_all_available_weighted_datasets.txt models\stopSignHard_v2_blend_cuda.pt models\final_carla_imitation_all_cuda.pt
```

## Public Comparison Models

| Checkpoint | Role |
| --- | --- |
| `models/allData_v1_mps.pt` | Earlier broad-data model kept for compatibility and comparison. |
| `models/teacherRefined_v1_cuda.pt` | Earlier CARLA teacher/recovery checkpoint. |
| `models/stopSignHard_v2_blend_cuda.pt` | Best pre-final blend checkpoint and final-model initialization point. |
| `models/final_carla_imitation_all_cuda.pt` | Current recommended model. |

## Observed Behavior

The final model is noticeably better at lane holding and recovery than earlier
checkpoints. The recovery test was good and the model is much improved, but it
is still not perfect. Remaining issues include slight steering twitchiness,
cautious or slow behavior, and rare-case weakness around intersections,
stop-sign behavior, and ambiguous lane markings.

## Data Scale Note

The project reached about a 1TB working/archive data footprint across raw
episodes, TAR shards, focus datasets, model artifacts, logs, and backups. The
final weighted training run used more than 16 million samples, but the model
still requires targeted data for the long-tail cases where behavior breaks
down. This is the main lesson from the final training cycle: total data volume
helps, but rare-case coverage matters more than simply adding broad driving
hours.
