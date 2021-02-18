# AlphaHydrogen

AlphaHydrogen is an open source OpenAI Gym environment that simulates the energy system of a residential community with distributed renewable power supply, fuel-cell vehicles, hydrogen stations, and power grid. Its objective is to advance the control of an integrated electricity-hydrogen building-vehicle-renewable energy system.

<!--
[[slides]](docs/slides.pdf)[[paper]](https://dl.acm.org/doi/10.1145/3408308.3427980)
-->

# Overview
Cleaner power production, distributed renewable generation, building-vehicle integration, hydrogen (H2) storage and associated energy infrastructures are promising candidates for transformation towards a carbon-neutrality community with district energy flexibility enhancement. AlphaHydrogen allows the easy implementation of advanced controll agents in a multi-agent setting to achieve customized goals: load shifting, CO2 emission reduction, operational cost saving, and etc. 

<img src="docs/overview.jpeg" data-canonical-src="docs/overview.jpeg" width="1000" />


# Code Usage
### Clone repository
```
git clone https://github.com/LBNL-ETA/City-Scale-Electricity-Use-Prediction
cd City-Scale-Electricity-Use-Prediction
```

### Set up the environment 
Set up the virtual environment with your preferred environment/package manager.

The instruction here is based on **conda**. ([Install conda](https://docs.anaconda.com/anaconda/install/))
```
conda create --name cityEleEnv python=3.8 -c conda-forge -f requirements.txt
conda activate cityEleEnv
```

### Repository structure
``bin``: Runnable programs, including Python scripts and Jupyter Notebooks

``data``: Raw data, including city-level electricity consumption and weather data

``docs``: Manuscript submitted version

``results``: Cleaned-up data, generated figures and tables


### Running
You can replicate our experiments, generate figures and tables used in the manuscript using the Jupyter notebooks saved in ``bin``: `section3.1 EDA.ipynb`, `section3.2 linear model.ipynb`, `section3.3 time-series model.ipynb`, `section3.4 tabular data model.ipynb`, `section4.1 model comparison.ipynb`, `section4.2 heat wave.ipynb`, `section4.3 convid.ipynb`

*Notes.*
- Official Documentation of [Facebook Prophet](https://facebook.github.io/prophet/).
- Official Documentation of [Microsoft lightGBM](https://github.com/Microsoft/LightGBM). 

### Feedback

Feel free to send any questions/feedback to: [Zhe Wang](mailto:zwang5@lbl.gov ) or [Tianzhen Hong](mailto:thong@lbl.gov)

### Citation

If you use our code, please cite us as follows:

<!--
```
@inproceedings{Chen2020COHORT,
author = {Chen, Bingqing and Francis, Jonathan and Pritoni, Marco and Kar, Soummya and Berg\'{e}s, Mario},
title = {COHORT: Coordination of Heterogeneous Thermostatically Controlled Loads for Demand Flexibility},
year = {2020},
isbn = {9781450380614},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
url = {https://doi.org/10.1145/3408308.3427980},
doi = {10.1145/3408308.3427980},
booktitle = {Proceedings of the 7th ACM International Conference on Systems for Energy-Efficient Buildings, Cities, and Transportation},
pages = {31–40},
numpages = {10},
keywords = {demand response, smart thermostats, TCLs, distributed control},
location = {Virtual Event, Japan},
series = {BuildSys '20}
}
```
-->
