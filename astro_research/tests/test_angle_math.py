from astro_daily.angle_math import angular_diff_signed, angular_distance, normalize_360


def test_angle_math_wraps_boundaries():
    assert normalize_360(-1) == 359
    assert angular_diff_signed(1, 359) == 2
    assert angular_distance(1, 359) == 2
    assert angular_distance(10, 190) == 180
