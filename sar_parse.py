import re
import csv
import argparse
import os.path

def parse_sar_log(input_file, output_file):
    """
    Parse SAR log file and convert to CSV
    
    Args:
    input_file (str): Path to the input SAR log file
    output_file (str): Path to the output CSV file
    """
    # Read the input file and replace special character
    with open(input_file, 'r', encoding='utf-8') as f:
        content = [line.replace('é', 'e') for line in f.readlines()]
    
    # Prepare CSV rows
    csv_rows = []
    headers = ['Timestamp', 'CPU', 'usr', 'nice', 'sys', 'iowait', 'steal', 'irq', 'soft', 'guest', 'gnice', 'idle']
    
    # Track the current timestamp
    current_timestamp = None
    
    # Parse the log file
    for line in content:
        # Skip lines with Linux header or other metadata
        if 'CPU' in line or 'Media:' in line:
            continue
        
        # Match timestamp lines
        timestamp_match = re.match(r'(\d{2}:\d{2}:\d{2})\s+CPU', line)
        if timestamp_match:
            current_timestamp = timestamp_match.group(1)
            continue
        
        elements = line.split()
        if len(elements) < 2:
#           print("The input line does not contain enough data.")
            print(".")
        else:
            # Output the results
            row = [
                elements[0],  # Timestamp
                elements[1],  # CPU identifier
                float(elements[2].replace(',','.')),  # usr
                float(elements[3].replace(',','.')),  # nice
                float(elements[4].replace(',','.')),  # sys
                float(elements[5].replace(',','.')),  # iowait
                float(elements[6].replace(',','.')),  # steal
                float(elements[7].replace(',','.')),  # irq
                float(elements[8].replace(',','.')),  # soft
                float(elements[9].replace(',','.')),  # guest
                float(elements[10].replace(',','.')),  # gnice
                float(elements[11].replace(',','.'))  # idle
            ]
            csv_rows.append(row)
    
    # Write to CSV
    with open(output_file, 'w', newline='') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(headers)
        csv_writer.writerows(csv_rows)
    
    print(f"Parsed SAR log saved to {output_file}")
    print(f"Total rows parsed: {len(csv_rows)}")

def main():
    # Configure argument parser
    parser = argparse.ArgumentParser(description='Parse SAR log file and convert to CSV')
    parser.add_argument('input_file', help='Path to the input SAR log file')
    parser.add_argument('-o', '--output', help='Path to the output CSV file (optional)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist")
        return
    
    # Generate output filename if not provided
    if args.output:
        output_file = args.output
    else:
        # Use input filename with .csv extension
        base_name = os.path.splitext(args.input_file)[0]
        output_file = f"{base_name}.csv"
    
    # Process the file
    parse_sar_log(args.input_file, output_file)

if __name__ == "__main__":
    main()