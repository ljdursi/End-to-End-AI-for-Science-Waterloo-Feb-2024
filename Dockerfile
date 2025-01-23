# Copyright (c) 2024 NVIDIA Corporation.  All rights reserved.

# To build the docker container, run: $ sudo docker build -t openhackathons:ai-for-science .
# To run: $ sudo docker run --gpus all --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 -p 8888:8888 -p 8899:8899 -it --rm openhackathons:ai-for-science
# Finally, open http://127.0.0.1:8888/

# Select Base Image 
FROM nvcr.io/nvidia/physicsnemo/physicsnemo:25.03

# Install required python packages
RUN pip3 install gdown ipympl cdsapi
RUN pip3 install --upgrade nbconvert

# TO COPY the data 
COPY workspace/ /workspace/

<<<<<<< HEAD
RUN python3 /workspace/python/source_code/dataset_NS.py
RUN python3 /workspace/python/source_code/dataset_darcy.py

RUN pip install jupyterlab
RUN python -m pip install --upgrade pip setuptools wheel
RUN apt update && apt install ffmpeg -y

RUN pip install --no-cache-dir --no-deps -e git+https://github.com/NVIDIA/modulus-makani.git@v0.1.0#egg=makani  

RUN python3 /workspace/python/source_code/dataset_darcy.py

## Uncomment this line to run Jupyter notebook by default
CMD jupyter-lab --no-browser --allow-root --ip=0.0.0.0 --port=8888 --NotebookApp.token="" --notebook-dir=/workspace/python/
