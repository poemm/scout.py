import yaml
import sys
sys.path.append('pywebassembly')
import pywebassembly as wasm


verbose=0


###############
# world storage
# key-value pairs, keys are a unique address (otherwise overwrite), values are Account
# perhaps this will eventually become a merklized structure which can be handled by a database
world_storage = {}


#########
# account
# like eth1 acct, contains a wasm code
class Account:
  def __init__(self, address, bytecode, state_root):
    self.bytecode = bytecode[:]
    self.address = address[:]
    self.state_root = state_root[:]
    self.calldata = None
    self.module_memory = None
  


  def exec_(self, calldata):
    """
      The following function is used to call a given contract.
      This will "spin-up" a new VM, execute the contract, and output the contract's return values and gas used.
    """
    self.calldata = calldata[:]

    # spin-up a VM
    modules = {}		# all moduleinst's indexed by their names, used to call funcs and resolve exports
    registered_modules = {}	# all moduleinst's which can be imported from, indexed by their registered name
    store = wasm.init_store()	# done once and lasts for lifetime of this abstract machine

    # create host module
    def eth2_loadPreStateRoot(store,arg):
      if verbose: print("eth2_loadPreStateRoot")
      offset = arg[0]
      self.module_memory[offset:offset+32] = self.state_root[:]
      return store,[]

    def eth2_blockDataSize(store,arg):
      if verbose: print("eth2_blockDataSize", len(self.calldata))
      return store,[len(self.calldata)]

    def eth2_blockDataCopy(store,arg):
      if verbose: print("eth2_blockDataCopy")
      memory_offset = arg[0]
      calldata_offset = arg[1]
      length = arg[2]
      self.module_memory[memory_offset:memory_offset+length] = self.calldata[calldata_offset:calldata_offset+length]
      return store,[]

    def eth2_savePostStateRoot(store,arg):
      if verbose: print("eth2_savePostStateRoot", arg[0])
      offset = arg[0]
      self.state_root[:] = self.module_memory[offset:offset+32]
      return store,[]

    def eth2_pushNewDeposit(store,arg):
      if verbose: print("eth2_pushNewDeposit")
      offset = arg[0]
      length = arg[1]
      return store,[]

    def eth2_debugPrintMem(store,arg):
      if verbose: print("eth2_debugPrintMem")
      offset = arg[0]
      length = arg[1]
      print(self.module_memory[offset:offset+length])
      return store,[]

    wasm.alloc_func(store, [["i32"],[]], eth2_loadPreStateRoot)
    wasm.alloc_func(store, [[],["i32"]], eth2_blockDataSize)
    wasm.alloc_func(store, [["i32","i32","i32"],[]], eth2_blockDataCopy)
    wasm.alloc_func(store, [["i32"],[]], eth2_savePostStateRoot)
    wasm.alloc_func(store, [["i32","i32"],[]], eth2_pushNewDeposit)
    wasm.alloc_func(store, [["i32","i32"],[]], eth2_debugPrintMem)
    modules["env"] =      {"types":[[["i32"],[]],
                                    [[],["i32"]],
                                    [["i32","i32","i32"],[]],
                                    [["i32","i32"],[]],
                                   ],
                           "funcaddrs":[0,1,2,3,4,5],
                           "tableaddrs":[],
                           "memaddrs":[],
                           "globaladdrs":[],
                           "exports":[{"name":"eth2_loadPreStateRoot","value":["func",0]},
                                      {"name":"eth2_blockDataSize","value":["func",1]},
                                      {"name":"eth2_blockDataCopy","value":["func",2]},
                                      {"name":"eth2_savePostStateRoot","value":["func",3]},
                                      {"name":"eth2_pushNewDeposit","value":["func",4]},
                                      {"name":"eth2_debugPrintMem","value":["func",5]},
                                     ]
                          }

    # register the host module
    registered_modules["env"] = modules["env"]           		#register module "ethereum" to be import-able

    # instantiate module which contains the func to-be-called
    module = wasm.decode_module(self.bytecode)                          #get module as abstract syntax
    externvalstar = []			           	                #populate imports
    for import_ in module["imports"]:
      if import_["module"] not in registered_modules: return None #error
      importmoduleinst = registered_modules[import_["module"]]
      externval = None
      for export in importmoduleinst["exports"]:
        if export["name"] == import_["name"]:
          externval = export["value"]
      if externval == None: return None #error
      if externval[0] != import_["desc"][0]: return None #error
      externvalstar += [externval]
    store,moduleinst,ret = wasm.instantiate_module(store,module,externvalstar)

    # get its memory
    self.module_memory = store["mems"][0]["data"]

    # finally, call the function
    externval = wasm.get_export(moduleinst, "main")	#we want to call function "main"
    funcaddr = externval[1]				#the address of the funcname
    args = []
    store,ret = wasm.invoke_func(store,funcaddr,args)	#finally, invoke the function
    return ret








def parse_scout_yaml(yaml_filename):

  with open(yaml_filename, 'r') as stream:
    yaml_loaded = yaml.safe_load(stream)

  # get wasm filenames execution_scripts, a list of strings
  beacon_state = yaml_loaded["beacon_state"]
  execution_scripts = beacon_state["execution_scripts"]

  # get exec_env_prestates, a list of strings
  shard_pre_state = yaml_loaded["shard_pre_state"]
  exec_env_prestates = shard_pre_state["exec_env_states"]
  for i in range(len(exec_env_prestates)):
    exec_env_prestates[i] = bytearray.fromhex(exec_env_prestates[i])

  # get shard_blocks, a list of maps 'env' integer : 'data' string
  shard_blocks = yaml_loaded["shard_blocks"]
  for block in shard_blocks:
    block["data"] = bytearray.fromhex(block["data"])

  # get exec_env_poststates, a list of strings
  shard_post_state = yaml_loaded["shard_post_state"]
  exec_env_poststates = shard_post_state["exec_env_states"]
  for i in range(len(exec_env_poststates)):
    exec_env_poststates[i] = bytearray.fromhex(exec_env_poststates[i])

  return execution_scripts, exec_env_prestates, shard_blocks, exec_env_poststates








if __name__ == '__main__':

  if len(sys.argv)<2:
    print("usage: python3 scout.py helloworld.yaml")

  wasm_filenames, prestates, shard_blocks, poststates = parse_scout_yaml(sys.argv[1])
  if(verbose): print(wasm_filenames, prestates, shard_blocks, poststates)

  if len(wasm_filenames) != len(prestates) or len(prestates) != len(poststates):
      print("ERROR: different numbers of files, prestates, or poststates")

  # get bytecode from each wasm file
  bytecodes = []
  for filename in wasm_filenames:
    with open(filename, "rb") as binary_file:
      bytecodes.append(binary_file.read())

  # create each account with address, fill bytecode and prestate
  for i in range(len(wasm_filenames)):
    address = bytearray([0]*32)
    address[0:4] = i.to_bytes((i.bit_length() + 7) // 8, 'little')
    address += bytearray([0]*(32-len(address)))
    # instantiate
    account = Account(address, bytecodes[i], prestates[i])
    # register it globally
    world_storage[bytes(address)] = account
  
  # execute each call
  for i in range(len(shard_blocks)):
    env = shard_blocks[i]["env"]
    address = bytearray([0]*32)
    address[0:4] = env.to_bytes((env.bit_length() + 7) // 8, 'little')
    address += bytearray([0]*(32-len(address)))
    account = world_storage[bytes(address)]
    account.exec_(shard_blocks[i]["data"])
    
  # check post-states
  for i in range(len(poststates)):
    address = bytearray([0]*32)
    address[0:4] = i.to_bytes((i.bit_length() + 7) // 8, 'little')
    address += bytearray([0]*(32-len(address)))
    # get account from global state
    account = world_storage[bytes(address)]
    # compare account state against expected poststate
    errorFlag = 0
    if account.state_root != poststates[i]:
      print("error with poststate",i,"\n",account.state_root,"  actual\n",poststates[i],"  expected")
      errorFlag = 1
    if not errorFlag:
      print("passed")




""" GPL3 license
    Scout.py - Implmentation of Scout.
    Copyright (C) 2019  Paul Dworzanski

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
