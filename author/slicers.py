"""The slicers a batch can be exported for, and how each one reads the 3MF.

bambu    Bambu Studio project: full Bambu printer preset, flush matrices, prime tower, Bambu support settings.
orca     Bambu-family project with a generic Marlin-style printer. Used by Orca Slicer and the Orca-based
         forks (Creality Print, ElegooSlicer, Anycubic Slicer Next). Only the settings the batch needs are
         written; the slicer fills every other value from its own defaults and the user's own printer preset.
prusa    PrusaSlicer project (Slic3r_PE config and model files).
"""
SLICERS = {
    'bambu_studio': dict(label='Bambu Studio', family='bambu', app='BambuStudio-02.08.02.61', extra={}),
    'orca': dict(label='Orca Slicer', family='orca', app='BambuStudio-02.06.00.51', extra={'OrcaSlicer': '2.4.2'}),
    'creality_print': dict(label='Creality Print', family='orca', app='CrealityPrint-7.2.0.0', extra={}),
    'elegoo': dict(label='ElegooSlicer', family='orca', app='ElegooSlicer-1.5.3.5', extra={}),
    'anycubic': dict(label='Anycubic Slicer Next', family='orca', app='BambuStudio-02.06.00.51', extra={'OrcaSlicer': '2.4.2'}),
    'prusa': dict(label='PrusaSlicer', family='prusa', app='PrusaSlicer-2.9.0', extra={}),
}
DEFAULT_FOR_BRAND = {'Bambu Lab': 'bambu_studio', 'Creality': 'creality_print', 'Elegoo': 'elegoo', 'Anycubic': 'anycubic', 'Prusa': 'prusa'}

START_GCODE = ('G28 ; home\nG90\nM83\nM140 S[bed_temperature_initial_layer_single]\nM104 S[nozzle_temperature_initial_layer]\n'
               'M190 S[bed_temperature_initial_layer_single]\nM109 S[nozzle_temperature_initial_layer]\nG92 E0')
END_GCODE = 'M104 S0\nM140 S0\nG91\nG1 Z10 F600\nG90\nM84'

# Settings that exist once per filament slot in an Orca-family project.
PER_FILAMENT = dict(filament_type='PLA', nozzle_temperature='210', nozzle_temperature_initial_layer='210', filament_diameter='1.75',
                    filament_density='1.24', filament_flow_ratio='1', filament_max_volumetric_speed='15', filament_cost='0',
                    filament_map='1', filament_settings_id='Generic PLA')

def orca_settings(palette, plates, printer, support=None):
    """project_settings.config for an Orca-family slicer, sized to the palette (one entry per filament slot)."""
    n = len(palette); w, d, h = printer['bed']
    cfg = {'printable_area': ['0x0', f'{w:g}x0', f'{w:g}x{d:g}', f'0x{d:g}'], 'printable_height': f'{h:g}', 'nozzle_diameter': ['0.4'],
           'gcode_flavor': 'marlin2', 'use_relative_e_distances': '1', 'layer_change_gcode': 'G92 E0', 'change_filament_gcode': 'M600',
           'machine_start_gcode': START_GCODE, 'machine_end_gcode': END_GCODE, 'single_extruder_multi_material': '1',
           'extruder_colour': [''], 'extruder_offset': ['0x0'], 'extruder_type': ['Direct Drive'], 'printer_extruder_id': ['1'],
           'nozzle_volume': ['0'], 'filament_colour': [c for _, c in palette], 'flush_multiplier': ['0.3'],
           'flush_volumes_matrix': ['0' if i == j else '140' for i in range(n) for j in range(n)], 'flush_volumes_vector': ['140'] * (2 * n),
           'enable_prime_tower': '1' if any(p['tower'] for p in plates) else '0', 'prime_tower_width': '60',
           'wipe_tower_x': [str(p['tower'][0] + 8 if p['tower'] else 0) for p in plates],
           'wipe_tower_y': [str(p['tower'][1] + 8 if p['tower'] else 0) for p in plates],
           'brim_type': 'no_brim', 'skirt_loops': '0', 'enable_support': '0', 'support_type': 'normal(auto)',
           'from': 'project', 'name': 'Filament Labels', 'version': '02.06.00.51', 'printer_settings_id': 'Generic Marlin printer',
           'print_settings_id': 'Filament Labels', 'printer_model': '', 'different_settings_to_system': [''] * (n + 2)}
    for key, value in PER_FILAMENT.items():
        cfg[key] = [value] * n
    if support:
        cfg.update(support)
        cfg.update(support_filament='0', support_interface_filament='0')
    return cfg
