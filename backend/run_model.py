import os
import subprocess
import sys
import logging

import argparse
# --- Configuration ---
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# --- Define project paths ---
# The script is in 'backend/', so we get its absolute path.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_GENERATOR_PATH = os.path.join(BASE_DIR, 'csv_generator')
FLOOD_DETECTOR_PATH = os.path.join(BASE_DIR, 'flood_detector')
FLOOD_MAPPER_PATH = os.path.join(BASE_DIR, 'flood_mapper')


def run_step(script_name, working_dir, step_description):
    """
    Runs a python script as a subprocess in a specified directory.

    Args:
        script_name (str): The name of the python script to run (e.g., 'generator.py').
        working_dir (str): The absolute path to the directory to run the script from.
        step_description (str): A human-readable description of the step.
    """
    logging.info(f"--- Running Step: {step_description} ---")
    
    # Ensure we use the same Python interpreter that is running this script.
    python_executable = sys.executable
    command = [python_executable, script_name]
    
    try:
        # Using capture_output=True and text=True to get stdout/stderr.
        # check=True will raise CalledProcessError on non-zero exit codes.
        result = subprocess.run(
            command,
            cwd=working_dir,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        logging.info(f"Successfully completed: {step_description}")
        if result.stdout:
            logging.debug(result.stdout)
    except FileNotFoundError:
        logging.error(f"Script '{script_name}' not found in '{working_dir}'. Aborting.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error(f"Step '{step_description}' failed with exit code {e.returncode}.")
        logging.error(f"Error output:\n{e.stderr}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during '{step_description}': {e}")
        sys.exit(1)


def main():
    """
    Main function to orchestrate the entire model pipeline.
    Parses command-line arguments to allow for flexible execution.
    """
    # Define the sequence of steps to run, using unique keys for each step
    pipeline_steps = {
        "csv_generator": ("generator.py", CSV_GENERATOR_PATH, "CSV Generator"),
        "flood_detector": ("combine.py", FLOOD_DETECTOR_PATH, "Flood Detector Model Suite"),
        "flood_mapper": ("run_analysis.py", FLOOD_MAPPER_PATH, "Flood Mapper Analysis"),
    }

    parser = argparse.ArgumentParser(description="Run the full flood model pipeline or parts of it.")
    parser.add_argument(
        '--steps',
        nargs='+',
        choices=pipeline_steps.keys(),
        help=f"Run only the specified steps. Choose from: {', '.join(pipeline_steps.keys())}"
    )
    parser.add_argument(
        '--skip',
        nargs='+',
        choices=pipeline_steps.keys(),
        help="Skip the specified steps."
    )
    parser.add_argument(
        '--start-at',
        choices=pipeline_steps.keys(),
        help="Start execution from the specified step."
    )
    parser.add_argument(
        '--list-steps',
        action='store_true',
        help="List all available pipeline steps and exit."
    )
    args = parser.parse_args()

    if args.list_steps:
        print("Available pipeline steps:")
        for name, (_, _, description) in pipeline_steps.items():
            print(f"  - {name}: {description}")
        sys.exit(0)

    logging.info(">>> Starting Full Model Pipeline Execution <<<")

    steps_to_run = list(pipeline_steps.keys())

    if args.steps:
        steps_to_run = [step for step in steps_to_run if step in args.steps]
    if args.skip:
        steps_to_run = [step for step in steps_to_run if step not in args.skip]
    if args.start_at:
        try:
            start_index = list(pipeline_steps.keys()).index(args.start_at)
            steps_to_run = [step for step in steps_to_run if list(pipeline_steps.keys()).index(step) >= start_index]
        except ValueError:
            pass # Invalid start_at will be ignored if not in the original list

    for step_name in steps_to_run:
        script, path, description = pipeline_steps[step_name]
        run_step(script, path, description)
        
    logging.info(">>> All pipeline steps completed successfully! <<<")


if __name__ == "__main__":
    main()
