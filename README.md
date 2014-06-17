hydropick
=========

Semi-automated Sediment picking GUI and algorithms for SDI multifrequency depth sounders 


command line
------------

```    
usage: hydropick [-h] [--import DIR] [--with-picks] [-v] [-q] [-d]
                 [--tide-gauge TIDE_GAUGE] [--export POINTS_FILE]

Hydropick: a hydrological survey editor

optional arguments:
  -h, --help            show this help message and exit
  --import DIR          survey data to import
  --with-picks          if included, then pre and pickfiles will be imported
  -v, --verbose         verbose logging
  -q, --quiet           quiet logging
  -d, --debug           debug logging
  --tide-gauge TIDE_GAUGE
                        autogenerate tide file from this USGS gauge
  --export POINTS_FILE  survey points file to export to

```


For example, to open hydropick for a particular survey:

    hydropick --import CorpusChristi/2012/SurveyData/

Application data is saved in a project directory. If one doesn't exist, it is automatically created. creates a project directory, in this case it would be `CorpusChristi/2012/SurveyData/CorpusChristi_2012-project/`.


Before exporting survey points, you'll need to create a tide file. To generate a tide file from a USGS NWIS gauge:

    hydropick --import CorpusChristi/2012/SurveyData/ --tide-gauge 08164525
    
This will create a tide file named: `CorpusChristi/2012/SurveyData/CorpusChristi_2012-project/tide_file.txt` that can be edited as needed.

Then, to export:

    hydropick --import CorpusChristi/2012/SurveyData/  --export output_file.txt
    
Will create a file named `output_file.txt` that contains the exported survey points.
    
