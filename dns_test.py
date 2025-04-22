import paramiko
import time
import subprocess
from datetime import datetime
import os
import sys
import argparse

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Execute DNS performance tests.')
    parser.add_argument('test_type', choices=['dnsfw_no', 'dnsfw_rpz', 'dnsfw_xdp'],
                       help='Type of test to be executed')
    
    # Create a mutually exclusive group for percentage arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--percent', type=int, choices=range(10, 100, 10),
                      help='Percentage of malicious domains in the test (10-90 in steps of 10)')
    group.add_argument('--all-percents', action='store_true',
                      help='Run tests for all percentages (10-90 in steps of 10)')
    
    parser.add_argument('--wait-time', type=int, default=10,
                       help='Wait time in seconds between sequential tests (default: 10)')
    
    return parser.parse_args()

def get_process_pid(ssh, process_name):
    """Get PID of a process using pgrep"""
    stdin, stdout, stderr = ssh.exec_command(f'pgrep {process_name}')
    pid = stdout.read().decode().strip()
    return pid if pid else None

def execute_local_command(command):
    """Execute command on local machine with better encoding handling"""
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='latin-1'
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Error executing local command: {stderr}")
            return False
        return True
    except Exception as e:
        print(f"Error executing local command: {e}")
        return False

def parse_sar_file(results_dir, sar_filename, output_suffix):
    """Execute SAR parser script on the downloaded file"""
    try:
        sar_input = os.path.join(results_dir, sar_filename)
        sar_output = os.path.join(results_dir, f'sar_output_{output_suffix}.csv')
        parser_cmd = f'python3 sar_parse.py {sar_input} -o {sar_output}'
        
        print("\nExecuting SAR parser...")
        if execute_local_command(parser_cmd):
            print(f"SAR parsing completed successfully. CSV output saved to {sar_output}")
        else:
            print("Failed to parse SAR output")
    except Exception as e:
        print(f"Error during SAR parsing: {e}")

def execute_ssh_commands(hostname, username, password, test_type, malicious_percent):
    """Execute the SSH commands for a single test"""
    try:
        # Initialize SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(f"Connecting to {hostname}...")
        
        # Connect to remote host
        ssh.connect(
            hostname=hostname,
            username=username,
            password=password,
            timeout=10
        )
        
        print("Successfully connected!")
        
        # Create timestamp for file naming (only date)
        timestamp = datetime.now().strftime("%Y%m%d")

        # Create local directory for results if it doesn't exist
        local_results_dir = f'results_{timestamp}'
        if not os.path.exists(local_results_dir):
            os.makedirs(local_results_dir)

        # Create a new channel for interactive shell
        channel = ssh.invoke_shell()
        time.sleep(1)
        
        # Become root
        print("Elevating to root privileges...")
        channel.send('sudo su -\n')
        time.sleep(2)
        channel.send(password + '\n')
        time.sleep(2)

        # Restarting named
        print("Restarting named...")
        channel.send('systemctl restart named\n')
        time.sleep(5)
    
        # Create suffix for file names
        file_suffix = f"{test_type}_{malicious_percent}"

        # Execute SAR command in background - with unique filename
        sar_output = f'/tmp/sar_output_{file_suffix}.txt'
        print("Executing SAR command...")
        channel.send(f'sar -u ALL -P ALL 1 -t 60 > {sar_output} &\n')
        time.sleep(3)

        # Start local dnspyre command
        print("Starting local dnspyre command...throughput")
        try:
            dnspyre_cmd = f'dnspyre -d 60s -c 60000 --server 192.168.0.72 --request-delay="1ms" --separate-worker-connections @output/domain_{malicious_percent}.txt'
            if not execute_local_command(dnspyre_cmd):
                print("Failed to execute dnspyre command")
        except Exception as e:
            print(f"Error during dnspyre execution: {e}")

        time.sleep(5)

        # Move requests.log to directory
        print("Moving requests.log latency to directory...")
        try:
            if not os.path.exists(local_results_dir):
                os.makedirs(local_results_dir)
            if not execute_local_command(f'mv requests_c_{file_suffix}.log {local_results_dir}/'):
                print(f"Failed to move requests.log to {local_results_dir}")
        except Exception as e:
            print(f"Error moving requests.log: {e}")

        time.sleep(1)  
        
        # Change permissions of output files
        channel.send(f'chmod 644 {sar_output}\n')
        time.sleep(1)
        
        # Use SCP to copy files from remote to local
        print("\nCopying result files from remote host...")
        
        # Create SFTP client
        sftp = ssh.open_sftp()
        
        # List of files to copy with new names including test type
        remote_files = [
            (sar_output, f'{local_results_dir}/sar_output_{file_suffix}.txt')
        ]
        
        # Copy each file
        for remote_path, local_path in remote_files:
            try:
                sftp.get(remote_path, local_path)
                print(f"Successfully copied {remote_path} to {local_path}")
            except Exception as e:
                print(f"Error copying {remote_path}: {e}")
        
        # Close SFTP client
        sftp.close()
        
        # Clean up remote temporary files
        print("\nCleaning up remote temporary files...")
        channel.send(f'rm -f {sar_output}\n')
        
        # Execute SAR parser on the downloaded file
        parse_sar_file(local_results_dir, f'sar_output_{file_suffix}.txt', file_suffix)
        
        print("\nAll commands executed successfully!")
        print(f"Results have been saved in the '{local_results_dir}' directory")
        
        return True
        
    except paramiko.AuthenticationException:
        print("Authentication failed. Please check username and password.")
        return False
    except paramiko.SSHException as ssh_exception:
        print(f"SSH exception occurred: {ssh_exception}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    finally:
        try:
            ssh.close()
            print("SSH connection closed.")
        except:
            pass

def run_single_test(test_type, percent, hostname, username, password):
    """Run a test with a specific percentage"""
    print(f"\n{'='*60}")
    print(f"Starting test for {test_type} with {percent}% malicious domains")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*60)
    
    success = execute_ssh_commands(hostname, username, password, test_type, percent)
    
    print(f"\nCompleted test for {test_type} with {percent}% malicious domains")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return success

def run_all_tests(test_type, hostname, username, password, wait_time):
    """Run tests for all percentages from 10 to 90"""
    percentages = list(range(10, 100, 10))  # 10, 20, 30, ..., 90
    
    print(f"\nStarting test sequence for {test_type}")
    print(f"Total tests to run: {len(percentages)}")
    print(f"Overall start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    successful_tests = 0
    failed_tests = []
    
    for percent in percentages:
        if run_single_test(test_type, percent, hostname, username, password):
            successful_tests += 1
            print(f"\nSuccessfully completed {successful_tests}/{len(percentages)} tests")
        else:
            failed_tests.append(percent)
        
        # Wait a bit between tests to ensure all processes are properly closed
        if percent != percentages[-1]:  # Don't wait after the last test
            print(f"\nWaiting {wait_time} seconds before starting next test...")
            time.sleep(wait_time)
    
    print(f"\n{'='*60}")
    print("Test sequence completed!")
    print(f"Overall end time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Successful tests: {successful_tests}/{len(percentages)}")
    if failed_tests:
        print(f"Failed tests for percentages: {failed_tests}")
    print('='*60)
    
    return successful_tests == len(percentages)

if __name__ == "__main__":
    args = parse_arguments()
    
    # Connection parameters
    hostname = "192.168.0.72" # DNS Server
    username = "user"
    password = "pass"
    
    if args.all_percents:
        # Run tests for all percentages
        success = run_all_tests(args.test_type, hostname, username, password, args.wait_time)
        sys.exit(0 if success else 1)
    else:
        # Run a single test with the specified percentage
        success = run_single_test(args.test_type, args.percent, hostname, username, password)
        sys.exit(0 if success else 1)