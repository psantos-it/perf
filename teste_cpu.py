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
    parser.add_argument('malicious_percent', type=int, choices=[10, 20, 30, 40, 50, 60, 70, 80, 90],
                       help='Percentage of malicious domains in the test (10, 30, or 50)')
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

        # Restarting named
        print("Restarting named...")
        channel.send('systemctl restart named\n')
        time.sleep(5)

        # Create suffix for file names
        file_suffix = f"{test_type}_{malicious_percent}"

        # Execute restart named
        print("Executing named restart...")
        channel.send(f'/usr/bin/systemctl restart named \n')
        time.sleep(2)

        # Execute SAR command in background - with unique filename
        sar_output = f'/tmp/sar_output_{file_suffix}.txt'
        print("Executing SAR command...")
        channel.send(f'sar -u ALL -P ALL 1 -t 60 > {sar_output} &\n')
        time.sleep(1)

        # Start local dnspyre command
        print("Starting local dnspyre command...")
        try:
            dnspyre_cmd = f'dnspyre -d 60s -c 40000 --server 192.168.0.72 --request-delay="1ms" --separate-worker-connections @output/domain_{malicious_percent}.txt'
            if not execute_local_command(dnspyre_cmd):
                print("Failed to execute dnspyre command")
        except Exception as e:
            print(f"Error during dnspyre execution: {e}")

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
    
    execute_ssh_commands(hostname, username, password, args.test_type, args.malicious_percent)