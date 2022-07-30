
import os
import json
import dataclasses

import mfc.run.case_dicts as case_dicts

from mfc.util.printer import cons

import mfc.util.common as common

@dataclasses.dataclass
class MFCInputFile:
    filename:     str
    case_dirpath: str
    case_dict:    dict
    args:         dict


    def __generate_inp(self, target_name: str) -> None:
        MASTER_KEYS: list = case_dicts.get_input_dict_keys(target_name)

        # Create Fortran-style input file content string
        dict_str = ""
        for key,val in self.case_dict.items():
            if key in MASTER_KEYS:
                dict_str += f"{key} = {val}\n"
                continue
                
            if key not in case_dicts.PRE_PROCESS  and \
               key not in case_dicts.POST_PROCESS and \
               key not in case_dicts.SIMULATION:
                raise common.MFCException(f"MFCInputFile::dump: Case parameter '{key}' is not used by any MFC code. Please check your spelling or add it as a new parameter.")

        contents = f"&user_inputs\n{dict_str}&end/\n"

        # Save .inp input file
        common.file_write(f"{self.case_dirpath}/{target_name}.inp", contents)


    def __generate_fpp(self, target_name: str) -> None:
        # === case.fpp ===
        filepath = f"{os.getcwd()}/src/common/case.fpp"
        content  = f"""\
! This file was generated by MFC. It is only used if the --hard-code option is
! passed to ./mfc.sh run, enabling a GPU-oriented optimization that hard-codes
! some case parameters in order to improve runtime performance.

#:set MFC_HARD_CODE = {self.args["hard_code"]}
"""


        if self.args["hard_code"]:
            content = content + f"""
#:set weno_polyn = {int((self.case_dict["weno_order"] - 1) / 2)}
#:set nb         = {int(self.case_dict.get("nb", -100))}
#:set num_dims   = {1 + min(int(self.case_dict.get("n", 0)), 1) + min(int(self.case_dict.get("p", 0)), 1)}
"""


        # Check if this case already has a case.fpp file.
        # If so, we don't need to generate a new one, which
        # would cause a partial and unnecessary rebuild.
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                lhs = [ l.strip() for l in f.read().splitlines() if not common.isspace(l) ]
                rhs = [ l.strip() for l in content.splitlines()  if not common.isspace(l) ]

                if lhs == rhs:
                    return


        common.file_write(filepath, content)


    # Generate case.fpp & [target_name].inp
    def generate(self, target_name: str) -> None:
        self.__generate_inp(target_name)
        self.__generate_fpp(target_name)


# Load the input file
def load(args: dict) -> MFCInputFile:
    filename: str = args["input"].strip()

    cons.print(f"Acquiring [bold magenta]{filename}[/bold magenta]...")

    dirpath:    str  = os.path.abspath(os.path.dirname(filename))
    dictionary: dict = {}

    if not os.path.exists(filename):
        raise common.MFCException(f"Input file '{filename}' does not exist. Please check the path is valid.")

    if filename.endswith(".py"):
        (json_str, err) = common.get_py_program_output(filename)

        if err != 0:
            raise common.MFCException(f"Input file {filename} terminated with a non-zero exit code. Please make sure running the file doesn't produce any errors.")
    elif filename.endswith(".json"):
        json_str = common.file_read(filename)
    else:
        raise common.MFCException("Unrecognized input file format. Only .py and .json files are supported. Please check the README and sample cases in the samples directory.")
    
    try:
        dictionary = json.loads(json_str)
    except Exception as exc:
        raise common.MFCException(f"Input file {filename} did not produce valid JSON. It should only print the case dictionary.\n\n{exc}\n")

    return MFCInputFile(filename, dirpath, dictionary, args)
