import paramiko
import time
import subprocess
from datetime import datetime
import os
import sys
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description='Execute DNS performance tests.')
    parser.add_argument('test_type', choices=['dnsfw_no', 'dnsfw_rpz', 'dnsfw_xdp'],
                       help='Type of test to be executed')
    return parser.parse_args()

def get_process_pid(ssh, process_name):
    """Get PID of a process using pgrep"""
    stdin, stdout, stderr = ssh.exec_command(f'pgrep {process_name}')
    pid = stdout.read().decode().strip()
    return pid if pid else None

def execute_local_command(command):
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

def execute_ssh_commands(hostname, username, password, test_type):
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

        #Execute SAR command in background - with unique filename
        sar_output = f'/tmp/sar_output_{test_type}.txt'
        print("Executing SAR command...")
        channel.send(f'sar -u ALL -P ALL 1 -t 60 > {sar_output} &\n')
        time.sleep(3)

        #Start local resperf command
        print("Starting local resperf command...throughput")
        try:
            resperf_cmd = f'resperf-report -R -s 192.168.0.72 -d query_file.txt -vv'
            if not execute_local_command(resperf_cmd):
                print("Failed to execute resperf command")
        except Exception as e:
            print(f"Error during resperf execution: {e}")

        time.sleep(5)
   
        # Change permissions of output files to allow copying
        if test_type == 'dnsfw_xdp':
            channel.send(f'chmod 644 {sar_output}\n')
        else:
            channel.send(f'chmod 644 {sar_output} \n')
        time.sleep(1)
        
        # Use SCP to copy files from remote to local
        print("\nCopying result files from remote host...")
        
        # Create SFTP client
        sftp = ssh.open_sftp()
        
        # List of files to copy with new names including test type
        remote_files = [
            (sar_output, f'{local_results_dir}/sar_output_{test_type}.txt')
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
        if test_type == 'dnsfw_xdp':
            channel.send(f'rm -f {sar_output} \n')
        else:
            #channel.send(f'rm -f {sar_output} {pidstat_named_output}\n')
            channel.send(f'rm -f {sar_output} \n')
        
        # Execute SAR parser on the downloaded file
        parse_sar_file(local_results_dir, f'sar_output_{test_type}.txt', test_type)
        
        print("\nAll commands executed successfully!")
        print(f"Results have been saved in the '{local_results_dir}' directory")
        
    except paramiko.AuthenticationException:
        print("Authentication failed. Please check username and password.")
    except paramiko.SSHException as ssh_exception:
        print(f"SSH exception occurred: {ssh_exception}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        try:
            ssh.close()
            print("SSH connection closed.")
        except:
            pass

if __name__ == "__main__":
    args = parse_arguments()
    
    # Connection parameters
    hostname = "192.168.0.72" # DNS Server
    username = "user"
    password = "pass"  
    
    execute_ssh_commands(hostname, username, password, args.test_type)