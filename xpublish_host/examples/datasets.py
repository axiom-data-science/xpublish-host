import xarray as xr


def simple():
    return xr.Dataset({'count': ('x', [1, 2, 3])})


def kwargs(varname, values=None):
    return xr.Dataset({varname: ('x', values)})
