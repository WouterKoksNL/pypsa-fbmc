
from pathlib import Path

def main(
        
        file_paths
        ):
    pass


if __name__ == "__main__":
    rm_list = [0.0, 0.1, 0.2, 0.3]
    fn_list = [f"n-0_RM_{str(r)}" for r in rm_list]
    case_name = "pypsa-eur-ua"
    base_path = Path(f"D:/NTNU/pypsa-fbmc-networks/results/{case_name}")
    file_paths = [Path(base_path) / fn for fn in fn_list]
    main()