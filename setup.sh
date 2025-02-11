#echo "mmdetection is not installing cython properly - it has to be installed from conda if this is conda python"
#conda install -y cython

echo "Installing pytorch and torchvision"
pip3 install torch==1.10.0+cu111 -f https://download.pytorch.org/whl/torch_stable.html

echo "Installing mmcv"
pip3 install mmcv-full==1.4.0 -f https://download.openmmlab.com/mmcv/dist/cu111/1.10.0/index.html

echo "Installing mmdetection"
echo "For more details, see: https://github.com/open-mmlab/mmdetection/blob/master/docs/get_started.md and https://github.com/open-mmlab/mmdetection"
python3 setup.py develop

pip3 install onnxruntime
pip3 install torchinfo

echo "This package depends on edgeai-torchvision:"
echo "Please visit https://github.com/TexasInstruments/edgeai-torchvision and clone and install that package."
