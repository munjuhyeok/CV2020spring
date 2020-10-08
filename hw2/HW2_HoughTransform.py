
import math
import glob
import numpy as np
from PIL import Image

# parameters

datadir = './data'
resultdir='./results'

sigma=2
threshold=0.03
rhoRes=2
thetaRes=math.pi/180
nLines=20

def shift_pixel(pixel_grid, axis, n):
    '''
    shift n pixel along axis

    Args:
        pixel_grid (ndarray): 2D numpy array representing an grayscale image.
        axis(int): axis to shift along
        n(int): how many pixel to shift

    Returns:
        ndarray: 2D numpy array representing an RGB image after shifting.
    '''
    sizeY, sizeX = pixel_grid.shape
    if axis == 0: #along y
        after_shift = np.tile(pixel_grid[sizeY-1],(sizeY,1)) if n>=0 else np.tile(pixel_grid[0],(sizeY,1))
        after_shift[max(0,-n):sizeY-n,:] = pixel_grid[max(0,+n):sizeY+n, :]
    elif (axis == 1): #along x
        after_shift = np.tile(pixel_grid[:,sizeX-1].reshape(-1,1),sizeX) if n>=0 else np.tile(pixel_grid[:,0].reshape(-1,1),sizeX)
        after_shift[:,max(0,-n):sizeX-n] = pixel_grid[:,max(0,+n):sizeX+n]
    else:
        raise NotImplementedError
    
    return after_shift

def getGaussianKernel(sigma):
    '''
    get gaussian kernal of std sigma
    consider up to 3*sigma, that is size of kernel is 1(center) + int(3*sigma)

    Args:
        sigma(float):std of the kernel

    Returns:
        ndarray: 2D numpy array representing an gaussian kernel.
    '''
    halfSize = int(3*sigma) # half of size-1 indeed
    dist1dSq = np.square(np.arange(-halfSize,halfSize+1))
    dist2dSq = dist1dSq.reshape(-1,1)+dist1dSq

    kernel = np.exp(-0.5*dist2dSq/np.square(sigma))

    return kernel/np.sum(kernel)    


def ConvFilter(Igs, G):
    # TODO ...
    sizeY = G.shape[0]
    sizeX = G.shape[1]
    toConv = []
    for i in range(-int(sizeY/2),sizeY-int(sizeY/2)):
        temp=[]
        for j in range(-int(sizeX/2),sizeX-int(sizeX/2)):
            temp.append(shift_pixel(shift_pixel(Igs,0,i),1,j))
        toConv.append(temp)
    toConv = np.asarray(toConv)
    #shape of toConv is (sizeY, sizeX, Igs.shape[0],Igs.shape[1])
    G = G.reshape(sizeY,sizeX,1,1)

    Iconv = np.sum(toConv*G,axis=(0,1))

    return Iconv

def EdgeDetection(Igs, sigma):
    # TODO ...
    gk = getGaussianKernel(sigma)
    Igs = ConvFilter(Igs, gk)
    sobelX = np.asarray([[-1,0,1],[-2,0,2],[-1,0,1]])
    sobelY = np.asarray([[1,2,1],[0,0,0],[-1,-2,-1]])
    Ix = ConvFilter(Igs,sobelX)
    Iy = ConvFilter(Igs,sobelY)
    Im = np.sqrt(np.square(Ix)+np.square(Iy))
    Io = np.arctan(Iy/Ix)

    return Im, Io, Ix, Iy

def nonMaximumSuppresion(Im, Io):
    '''
    non-maxmimum suppression

    Args:
        Im(ndarray): 2D numpy array representing an edge magnitude image.
        Io(ndarray): 2D numpy array representing an edge orientation image(rad).

    Returns:
        ndarray: 2D numpy array representing edge image after non-maximum suppresion

    '''
    sizeY, sizeX = Im.shape
    nms = np.zeros_like(Im)
    for i in range(sizeY):
        for j in range(sizeX):
            try:
                angle = Io[i,j]
                if (angle < -np.pi/4):
                    temp = np.tan(angle + np.pi/2)
                    p = (1-temp)*Im[i+1,j]+temp*Im[i+1,j+1]
                    q = (1-temp)*Im[i-1,j]+temp*Im[i-1,j-1]
                elif (angle < 0):
                    temp = np.tan(-angle)
                    p = (1-temp)*Im[i,j+1]+temp*Im[i+1,j+1]
                    q = (1-temp)*Im[i,j-1]+temp*Im[i-1,j-1]
                elif (angle < np.pi/4):
                    temp = np.tan(angle)
                    p = (1-temp)*Im[i,j+1]+temp*Im[i-1,j+1]
                    q = (1-temp)*Im[i,j-1]+temp*Im[i+1,j-1]
                elif (angle <= np.pi/2):
                    temp = np.tan(np.pi/2-angle)
                    p = (1-temp)*Im[i-1,j]+temp*Im[i-1,j+1]
                    q = (1-temp)*Im[i+1,j]+temp*Im[i+1,j-1]
                else:
                    pass
            except IndexError:
                pass
            if(Im[i,j]>=q and Im[i,j]>=p):
                nms[i,j] = Im[i,j]

    return nms

def doubleThresholding(Im, threshold1, threshold2):

    result = np.zeros_like(Im,dtype = np.uint8)
    result[Im<threshold1] = 0
    result[np.logical_and(Im>=threshold1,Im<threshold2)] = 127
    result[Im>=threshold2] = 255
    return result

def edgeTracking(Im):
    result = Im.copy()
    
    while(True): #iterate until no update
        isWeak = result ==127
        neighbor = []
        for i in range(-1,2):
            for j in range(-1,2):
                if(i==0 and j==0): continue
                neighbor.append(shift_pixel(shift_pixel(result,0,i),1,j))
        neighbor = np.asarray(neighbor)
        continuity = np.max(neighbor,axis=0) == 255
        weakToStrong = np.logical_and(isWeak,continuity)
        if not np.any(weakToStrong):
            break
        result[weakToStrong] = 255

    result[np.logical_and(isWeak,np.invert(continuity))] = 0

    return result

def Canny(Igs, sigma, threshold1, threshold2):
    '''
    Canny Edge Operator

    Args:
        Igs(ndarray): 2D numpy array representing an grayscale image.
        sigma(float): std of the gaussian kernel to blur with
        threshold1(float): if edge magnitude smaller than this, definitely not an edge.
                            else, depends on context
        threshold2(float): if edge magnitude larger than this, definitely an edge.

    Returns:
        ndarray: 2D numpy array representing an grayscale image after applying Canny Edge Operator.
    '''
    
    Im, Io, _, _ = EdgeDetection(Igs, sigma)
    result = nonMaximumSuppresion(Im, Io)
    result = doubleThresholding(result, threshold1, threshold2)
    result = edgeTracking(result)

    return result



def HoughTransform(Im,threshold, rhoRes, thetaRes):
    # TODO ...
    sizeY, sizeX = Im.shape
    rhoMax = np.sqrt(np.square(sizeY)+np.square(sizeX))
    rhoStep = rhoMax/rhoRes
    thetaStep = 2*np.pi/thetaRes
    H = np.zeros((rhoRes, thetaRes), dtype=float)

    for y, x in zip(*np.where(Im>threshold)):
        for i in range(thetaRes):
            theta = i*thetaStep
            rho = x*np.cos(theta)+y*np.sin(theta)
            if(rho>0):
                H[int(rho/rhoStep),i] += 1
    print(H.dtype)



    return H

def HoughLines(H,rhoRes,thetaRes,nLines):
    # TODO ...


    return lRho,lTheta

def HoughLineSegments(lRho, lTheta, Im, threshold):
    # TODO ...


    return l

def main():

    # read images
    for img_path in glob.glob(datadir+'/*.jpg'):
        # load grayscale image
        img = Image.open(img_path).convert("L")

        Igs = np.array(img)


        # Image.fromarray(Canny(Igs, 1, 50, 100)).show()

        Igs = Igs / 255.


        # Hough function
        Im, Io, Ix, Iy = EdgeDetection(Igs, sigma)
        Im = nonMaximumSuppresion(Im, Io) #added
        Image.fromarray(doubleThresholding(Im, 0.1, 0.1)).show()
        rhoRes = 100
        thetaRes = 360
        H= HoughTransform(Im,threshold, rhoRes, thetaRes)
        Image.fromarray(H).show()
        lRho,lTheta =HoughLines(H,rhoRes,thetaRes,nLines)
        l = HoughLineSegments(lRho, lTheta, Im, threshold)

        # saves the outputs to files
        # Im, H, Im + hough line , Im + hough line segments


if __name__ == '__main__':
    main()