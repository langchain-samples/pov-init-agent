# Notebooks in Nimbus Workbench

## Creating a notebook server
1. In Nimbus Workbench, open **Notebooks** from the left navigation.
2. Click **New Notebook Server**.
3. Pick a **notebook image**. Choose a GPU-enabled image (for example the Jupyter data
   science image with CUDA) if you need GPUs; CPU-only images start faster.
4. Set **CPU** and **memory**, and under **GPUs** set the number of GPUs (0 for none).
5. Click **Launch**. When the status turns to Running, click **Connect** to open JupyterLab.

## Storage volumes and where to save files
Every notebook server mounts three locations:
- `/mnt/user` — your private, persistent home area. Only you can see it.
- `/mnt/shared` — a persistent volume shared with all users on the platform. Save files here
  when teammates need to see them.
- `/mnt/datasources` — read access to the data sources an administrator configured.

Anything written outside these paths (for example `/tmp`) is lost when the notebook server
restarts.

## Stopping idle notebooks
GPUs attached to a notebook server stay reserved while it runs, even when idle. Stop the
notebook server from the **Notebooks** page when you're done so the GPUs return to the pool;
your files under `/mnt/user` and `/mnt/shared` are kept.
