#!/usr/bin/python

#import fn_nmos 

path = "/disks/piprobe/qhc/tests/data"

def pulse_test(drain,height,width,edge):
  program_array = [drain,height,width,edge]
  erase_array = [drain*height,height*width,width*edge,edge*drain]
  return [program_array,erase_array]

### Pulse sensitivity test

# Test conditions
heights = [4,4.5,5,5.5,6]
widths = [5,50,500,5000]
edges = [2,5]
drains = [5,6,7,8,9,10,11,12]

for edge in edges:
  for drain in drains:
    for width in widths:
      for height in heights:
        data_arr = []
        data_arr = pulse_test(drain,height,width,edge)
        filename1 = "{0}/fn_nmos_program_{1}_{2}_{3}_{4}".format(path,drain,height,width,edge)
        filename2 = "{0}/fn_nmos_erase_{1}_{2}_{3}_{4}".format(path,drain,height,width,edge)
        f1 = open(filename1,'w')
        f2 = open(filename2,'w')
        for val in data_arr[0]:    # Program data
          s = str(val)
          f1.write(s + '\n')
        for val in data_arr[1]:    # Erase data
          s = str(val)
          f2.write(s + '\n')
