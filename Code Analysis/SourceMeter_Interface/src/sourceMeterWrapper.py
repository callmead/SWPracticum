import fnmatch
import os
import shlex
import shutil
import sys
from subprocess import Popen
from pandas import read_csv, concat
from constants import CLEAN_UP_SM_FILES, RESULTS_DIR, SOURCE_METER_JAVA_PATH, SOURCE_METER_PYTHON_PATH, \
    CLASS_KEEP_COL, METHOD_KEEP_COL, POSIX, DIR_SEPARATOR


def exec_metric_analysis(project_dir, project_name, project_type):
    run_cmd = [SOURCE_METER_PYTHON_PATH,
               "-projectBaseDir:" + project_dir,
               "-projectName:" + project_name,
               "-resultsDir:" + RESULTS_DIR,
               "-runMetricHunter:false",
               "-runFaultHunter:false",
               "-runDCF:false",
               "-runMET:true",
               "-runPylint:false"
               ] if project_type == "python" else \
        [SOURCE_METER_JAVA_PATH,
         "-projectBaseDir=" + project_dir,
         "-projectName=" + project_name,
         "-resultsDir=" + RESULTS_DIR,
         "-runAndroidHunter=false"
         "-runMetricHunter=false",
         "-runFaultHunter=false",
         "-runVulnerabilityHunter=false",
         "-runRTEHunter=false",
         "-runDCF=false",
         "-runMET=true",
         "-runFB=false",
         "-runPMD=true"
         ]
    Popen(run_cmd).wait() if POSIX else Popen(shlex.split(run_cmd, posix=POSIX)).wait()


def consolidate_metrics(project_name, project_type):
    # Consolidate Source Meter Metrics
    sc_results_dir = os.path.join(RESULTS_DIR, project_name, "java" if project_type == "java" else "python")
    latest_results_path = os.path.join(sc_results_dir, os.listdir(sc_results_dir)[0])
    class_file = os.path.join(latest_results_path, project_name + "-Class.csv")
    methods_file = os.path.join(latest_results_path, project_name + "-Method.csv")

    # Read class-level metrics and keep only certain columns
    tmp_f = read_csv(class_file)[CLASS_KEEP_COL]
    # Insert 'Level' column
    tmp_f.insert(0, 'Type of Smell', 'Class')
    # Insert Method-Level Columns and set value to '-'
    curr_column = len(CLASS_KEEP_COL) + 1
    for metric in set(METHOD_KEEP_COL) - set(CLASS_KEEP_COL):
        tmp_f.insert(curr_column, metric, '-')
        curr_column += 1
    class_portion = tmp_f

    # Read method-level metrics, keep only certain columns, and rename 'Path' column to 'Class'
    tmp_f = read_csv(methods_file)[METHOD_KEEP_COL]
    # Make every row in column 'Class' contain only the last token (class name) when splitting with DIR_SEPARATOR
    tmp_f['Path'] = tmp_f['Path']\
        .apply(lambda x: str(x)).apply(lambda x: x.split(DIR_SEPARATOR)[len(x.split(DIR_SEPARATOR)) - 1])
    # Insert 'Level' column
    tmp_f.insert(0, 'Type of Smell', 'Method')
    # Insert Class-Level Columns and set value to '-'
    curr_column = len(METHOD_KEEP_COL) + 1
    for metric in set(CLASS_KEEP_COL) - set(METHOD_KEEP_COL):
        tmp_f.insert(curr_column, metric, '-')
        curr_column += 1
    method_portion = tmp_f

    result = concat([class_portion, method_portion], sort=False)
    result = result.rename(columns={'LOC': 'Lines of Code',
                                    'CD': 'Comment-to-Code Ratio',
                                    'CBO': 'Number of Directly-Used Elements',
                                    'NOI': 'Number of Outgoing Invocations',
                                    'Path': 'Name of Owner Class',
                                    'NUMPAR': 'Number of Parameters'
                                    })
    result.to_csv(os.path.join(RESULTS_DIR, project_name, "metrics.csv"), index=False)

    # Clean up excess Source Meter files
    if CLEAN_UP_SM_FILES:
        clear_dir(sc_results_dir)


def clear_dir(directory):
    shutil.rmtree(directory)


def get_project_name(directory):
    proj_name_tokens = directory.split(DIR_SEPARATOR)
    return proj_name_tokens[len(proj_name_tokens) - 1]


def get_project_type(directory):
    java_files = [os.path.join(dirpath, f)
                  for dirpath, dirnames, files in os.walk(directory) for f in fnmatch.filter(files, '*.java')]
    python_files = [os.path.join(dirpath, f)
                    for dirpath, dirnames, files in os.walk(directory) for f in fnmatch.filter(files, '*.py')]
    return "java" if len(java_files) and len(java_files) > len(python_files) else "python"


def analyze_from_repo(url):
    url_tokens = url.split('/')
    proj_name = url_tokens[len(url_tokens) - 1].strip('.git')
    tmp_dir = os.path.join(os.getcwd(), "..", "tmp")
    curr_dir = os.getcwd()
    os.makedirs(tmp_dir)
    clone_cmd = ["git", "clone", url]
    os.chdir(tmp_dir)
    Popen(clone_cmd).wait() if POSIX else Popen(shlex.split(clone_cmd, posix=POSIX)).wait()
    proj_dir = os.path.join(os.getcwd(), os.listdir(tmp_dir)[0])
    os.chdir(curr_dir)
    proj_type = get_project_type(proj_dir)
    exec_metric_analysis(proj_dir, proj_name, proj_type)
    consolidate_metrics(proj_name, proj_type)
    shutil.rmtree(tmp_dir)


def analyze_from_path(proj_dir):
    if proj_dir[-1] == '/':
        proj_dir = proj_dir[:-1]
    proj_name = get_project_name(proj_dir)
    proj_type = get_project_type(proj_dir)
    exec_metric_analysis(proj_dir, proj_name, proj_type)
    consolidate_metrics(proj_name, proj_type)


def arg_type(arg):
    return "url" if "github.com" in arg else "path"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Error: Please pass an argument with a URL or the path to the project that will be analyzed."
    elif arg_type(sys.argv[1]) is "url":
        analyze_from_repo(sys.argv[1])
    elif os.path.isdir(sys.argv[1]):
        analyze_from_path(sys.argv[1])
    else:
        print "Error: The passed argument is not a url and it is not a valid directory."
