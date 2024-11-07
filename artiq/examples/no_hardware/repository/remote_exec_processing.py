import numpy as np
from numba import jit
from scipy.optimize import least_squares
import logging

# Set up logger for this module
logger = logging.getLogger(__name__)

@jit(nopython=True)
def compute_gaussian(r, img_w, img_h, gaussian_w, gaussian_h, gaussian_cx, gaussian_cy):
    # Compute a 2D Gaussian distribution over the image dimensions
    for y in range(img_h):
        for x in range(img_w):
            # Calculate the squared distance from the Gaussian center
            ds = ((gaussian_cx-x)/gaussian_w)**2
            ds += ((gaussian_cy-y)/gaussian_h)**2
            # Compute the Gaussian value at (x, y)
            r[x, y] = np.exp(-ds/2)

def fit(data, get_dataset):
    # Fit a Gaussian to the given data
    img_w, img_h = data.shape  # Get image dimensions

    def err(parameters):
        # Error function for least squares optimization
        r = np.empty((img_w, img_h))  # Create an empty array for the Gaussian
        compute_gaussian(r, img_w, img_h, *parameters)  # Compute Gaussian with current parameters
        r -= data  # Subtract the data from the Gaussian
        return r.ravel()  # Return the flattened error array

    # Initial guess for the Gaussian parameters
    guess = [
        get_dataset("rexec_demo.gaussian_w", 12),  # Width
        get_dataset("rexec_demo.gaussian_h", 15),  # Height
        get_dataset("rexec_demo.gaussian_cx", img_w/2),  # Center x
        get_dataset("rexec_demo.gaussian_cy", img_h/2)   # Center y
    ]
    # Perform least squares optimization to fit the Gaussian
    res = least_squares(err, guess)
    return res.x  # Return the optimized parameters

def get_and_fit():
    # Get data and fit a Gaussian to it
    if "dataset_db" in globals():
        logger.info("using dataset DB for Gaussian fit guess")

        def get_dataset(name, default):
            # Retrieve dataset value or use default if not found
            try:
                return dataset_db.get(name)
            except KeyError:
                return default
    else:
        logger.info("using defaults for Gaussian fit guess")

        def get_dataset(name, default):
            # Always use default values
            return default

    # Get picture data and fit Gaussian
    return fit(controller_driver.get_picture(), get_dataset)
