export type CountyProperties = {
  geo_point_2d: {
    lon: number;
    lat: number;
  };
  year: string;
  ste_code: string[];
  ste_name: string[];
  coty_code: string[];
  coty_name: string[];
  coty_area_code: string;
  coty_name_long: string[];
  coty_fp_code: string;
  coty_gnis_code: string;
};