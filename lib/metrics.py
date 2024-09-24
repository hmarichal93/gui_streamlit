"""
Module for computing important metrics
"""
import numpy as np
import pandas as pd

from shapely.geometry import Polygon, LineString

import numpy as np
import cv2
import datetime

from pathlib import Path

import pandas as pd
from shapely.geometry import Polygon, Point

from lib.image import Color, Drawing

from backend.labelme_layer import AL_AnnualRings


def fill_df(annual_ring_label_list, year_list, ew_lw_label_list, ring_area_list, ew_area_list, eccentricity_module_list,
            eccentricity_phase_list, ring_perimeter_list, pixels_millimeter_relation):

    df = pd.DataFrame(columns=["Annual Ring (label)", "EW/LW label", "Year",  # metadata
                               "Ring Area [mm2]",  # ring properties
                               "Cumulative Area [mm2]", "Cumulative Annual Radius [mm]", "Annual Ring Width [mm]",
                               # math operations on ring properties
                               "Area EW [mm2]",  # ring properties
                               "Cumulative R(n-1) + EW(n) Area [mm2]", "Cumulative EW Radius [mm]", "EW Width [mm]",
                               # math operations on ring properties
                               "Area LW [mm2]",  # ring properties
                               "LW Width [mm]",  # math operations on ring properties
                               "Area LW/(LW +EW) (-)", "Width LW/(LW +EW) (-)",  # math operations on ring properties
                               "Eccentricity Module [mm]", "Eccentricity Phase [°]",  # ring properties
                               "Perimeter [mm]",  # ring properties
                               "Ring Similarity Factor [0-1]"]  # math operations on ring properties
                      )

    df["Annual Ring (label)"] = annual_ring_label_list
    df["EW/LW label"] = ew_lw_label_list
    df["Year"] = year_list

    df["Ring Area [mm2]"] = np.array(ring_area_list) * (pixels_millimeter_relation ** 2)
    df["Cumulative Area [mm2]"] = df["Ring Area [mm2]"].cumsum()
    df["Cumulative Annual Radius [mm]"] = np.sqrt(df["Cumulative Area [mm2]"] / np.pi)
    annual_ring_width_list = df["Cumulative Annual Radius [mm]"].diff()
    annual_ring_width_list[0] = df["Cumulative Annual Radius [mm]"].iloc[0]
    df["Annual Ring Width [mm]"] = np.array(annual_ring_width_list)

    df["Area EW [mm2]"] = np.array(ew_area_list) * (pixels_millimeter_relation ** 2)
    df["Cumulative R(n-1) + EW(n) Area [mm2]"] = (df["Cumulative Area [mm2]"].shift(1) + df["Area EW [mm2]"]).fillna(0)
    df["Cumulative EW Radius [mm]"] = np.sqrt(df["Cumulative R(n-1) + EW(n) Area [mm2]"] / np.pi)
    ew_ring_width_list = (df["Cumulative EW Radius [mm]"] - df["Cumulative Annual Radius [mm]"].shift(1)).fillna(0)
    df["EW Width [mm]"] = np.array(ew_ring_width_list)

    df["Area LW [mm2]"] = df["Ring Area [mm2]"] - df["Area EW [mm2]"]
    df["LW Width [mm]"] = df["Annual Ring Width [mm]"] - df["EW Width [mm]"]
    df["Area LW/(LW +EW) (-)"] = df["Area LW [mm2]"] / df["Ring Area [mm2]"]
    df["Width LW/(LW +EW) (-)"] = df["LW Width [mm]"] / df["Annual Ring Width [mm]"]
    df["Eccentricity Module [mm]"] = np.array(eccentricity_module_list) * pixels_millimeter_relation
    df["Eccentricity Phase [°]"] = np.array(eccentricity_phase_list)
    df["Perimeter [mm]"] = np.array(ring_perimeter_list) * pixels_millimeter_relation
    df["Ring Similarity Factor [0-1]"] = 1 - (df["Perimeter [mm]"] - 2 * np.pi * df["Cumulative Annual Radius [mm]"]) / \
                                         df["Perimeter [mm]"]
    df = df.round(2)
    return df

def compute_angle(vector):
    x, y = vector
    angle_radians = np.arctan2(y, x)
    angle_degrees = np.degrees(angle_radians)
    angle_360 = angle_degrees if angle_degrees >= 0 else angle_degrees + 360
    return angle_360

def extract_ring_properties(annual_rings_list, year, plantation_date):
    pith = Point(0, 0)
    #image_full = image.copy()
    ring_area_list = []
    ew_area_list = []
    lw_area_list = []
    ring_perimeter_list = []
    eccentricity_module_list = []
    eccentricity_phase_list = []
    year_list = []
    annual_ring_label_list = []
    ew_lw_label_list = []

    for idx, ring in enumerate(annual_rings_list):
        #area
        ring_area_list.append(ring.area)
        latewood_area = ring.late_wood.area if ring.late_wood is not None else 0
        earlywood_area = ring.early_wood.area if ring.early_wood is not None else 0
        ew_area_list.append(earlywood_area)
        lw_area_list.append(latewood_area)

        #eccentricity
        if idx == 0:
            pith = ring.centroid
        ring_centroid = ring.get_centroid()
        eccentricity_module = ring_centroid.distance(pith)
        if eccentricity_module == 0:
            eccentricity_phase = 0
        else:
            #change reference y-axis to the opposite direction
            convert_to_numpy = lambda point: np.multiply(np.array([point.coords.xy[0], point.coords.xy[1]]).squeeze(), np.array([-1, 1]))
            numpy_ring_centroid = convert_to_numpy(ring_centroid).squeeze()

            numpy_pith = convert_to_numpy(pith).squeeze()
            #change origin to pith
            numpy_ring_centroid_referenced_to_pith = numpy_ring_centroid - numpy_pith
            #normalize
            numpy_ring_centroid_referenced_to_pith_normalized = numpy_ring_centroid_referenced_to_pith / np.linalg.norm(numpy_ring_centroid_referenced_to_pith)

            angle = compute_angle(numpy_ring_centroid_referenced_to_pith_normalized)
            eccentricity_phase = angle

        eccentricity_module_list.append(eccentricity_module)
        eccentricity_phase_list.append(eccentricity_phase)
        ring_perimeter_list.append(ring.length)

        #metadata
        year_list.append( year.year)
        annual_ring_label_list.append(ring.main_label)
        ew_lw_label_list.append(ring.secondary_label)
        #save results
        year = year + datetime.timedelta(days=365) if plantation_date else year - datetime.timedelta(days=365)

    return annual_ring_label_list, year_list, ew_lw_label_list, ring_area_list, ew_area_list, eccentricity_module_list, eccentricity_phase_list, ring_perimeter_list

def debug_images(annual_rings_list, df, image_path, output_dir):
    image = cv2.imread(image_path)
    image_full = image.copy()
    for idx, ring in enumerate(annual_rings_list):
        #eccentricity
        if idx == 0:
            pith = ring.centroid
        ring_centroid = ring.get_centroid()
        image_full = ring.draw_rings( image_full, thickness=3)
        thickness= 3
        image_debug = ring.draw(image.copy(), full_details=True, opacity=0.1)
        image_debug = Drawing.curve(ring.exterior.coords, image_debug, Color.black, thickness)
        inner_points = np.array([list(interior.coords) for interior in ring.interiors]).squeeze()
        if len(inner_points) > 0:
            aux_poly = Polygon(inner_points)
            image_debug = Drawing.curve(aux_poly.exterior.coords, image_debug, Color.black, thickness)
            #draw arrow from centroid to pith
            image_debug = Drawing.arrow(image_debug, pith, ring_centroid, Color.red, thickness=3)
        output_name = f"{output_dir}/{ring.main_label}.png"
        cv2.imwrite(output_name, image_debug)

    cv2.imwrite(f"{output_dir}/rings.png", image_full)

    return
def export_results( labelme_latewood_path : str, labelme_earlywood_path : str, image_path : str, metadata: dict,
                   output_dir="output",  plantation_date=True, draw=False):
    #metadata
    year = metadata["year"]
    year = datetime.datetime(year, 1, 1)

    pixels_millimeter_relation = float(metadata["pixels_millimeter_relation"])

    al_annual_rings = AL_AnnualRings(late_wood_path=Path(labelme_latewood_path),
                                     early_wood_path=Path(labelme_earlywood_path))
    annual_rings_list = al_annual_rings.read()

    (annual_ring_label_list, year_list, ew_lw_label_list, ring_area_list, ew_area_list, eccentricity_module_list,
     eccentricity_phase_list, ring_perimeter_list) = extract_ring_properties(annual_rings_list, year, plantation_date)

    df = fill_df(
        annual_ring_label_list, year_list, ew_lw_label_list, ring_area_list, ew_area_list,
        eccentricity_module_list, eccentricity_phase_list, ring_perimeter_list, pixels_millimeter_relation
    )

    df.to_csv(f"{output_dir}/measures.csv", index=False)
    if draw:
        debug_images(annual_rings_list, df, image_path, output_dir)

    return



def main():
    root = "./input/C14/"
    image_path = f"{root}image.jpg"
    labelme_latewood_path = f"{root}latewood.json"
    labelme_earlywood_path = f"{root}earlywood.json"
    metadata = {
        "year": 1993,
        "pixels_millimeter_relation": 10 / 52
    }
    export_results(labelme_latewood_path, labelme_earlywood_path, image_path, metadata)




if __name__ == "__main__":
    main()