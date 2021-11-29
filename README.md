# avocado-cloud-scheduler

Scheduler and Executor for avocado-cloud testing.

# Usage

## 1. Setup

```bash
dnf install podman
```

## 2. Preparation

```bash
git clone https://github.com/virt-s1/avocado-cloud.git

cd avocado-cloud
podman build --rm --pull -t "avocado-cloud" . -f ./container/Dockerfile

podman inspect avocado-cloud:latest
```

## 3. Configuration

```bash
git clone https://github.com/schrht/avocado-cloud-scheduler.git

cd avocado-cloud-scheduler
vi config.toml
```

### 3.1. Enable a region

```bash
# Prepare image (example)
./utils/copy_image.sh -r cn-hangzhou -n redhat_8_5_x64_20G_alibase_20211117.qcow2 \
    -R cn-hangzhou -N redhat_8_5_x64_20G_alibase_20211117_copied.qcow2
./utils/copy_image.sh -r cn-hangzhou -n redhat_8_5_x64_20G_alibase_20211117_copied.qcow2 -R cn-beijing

# Prepare VSwitches (example)
./utils/create_vsw_for_region.sh -r cn-beijing

# Add to the config.toml
vi config.toml
```

## 4. Manual test
```bash
cd avocado-cloud-scheduler
./executor.py --flavor esx.i2.xlarge
```
