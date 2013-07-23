import numpy as np
import pyfits as pf
import matplotlib.pyplot as plt
from echelle_io import rechelletxt
from scipy.interpolate import interp1d
from scipy.integrate import trapz
from scipy.ndimage.filters import convolve
from matplotlib.ticker import FormatStrFormatter as FSF
import asciitable

c_ang = 2.99792458e18 #A s^-1
c_kms = 2.99792458e5 #km s^-1

Mg = np.array([5168.7605, 5174.1251, 5185.0479])

#Load real data
#wl,fl = np.loadtxt("GWOri_c/23.txt",unpack=True)
#Load normalized spectrum
wl,fl = np.loadtxt("GWOri_cn/23.txt",unpack=True)

#efile = rechelletxt()
#use order 36 for all testing
#wl,fl = efile[22]

#Limit huge file to necessary range
#ind = (w > (wl[0] - 10.)) & (w < (wl[-1] + 10))

wl_file = pf.open("WAVE_PHOENIX-ACES-AGSS-COND-2011.fits")
w = wl_file[0].data
wl_file.close()
#ind = (w > 3800.) & (w < 10000.)
ind = (w > (wl[0] - 10.)) & (w < (wl[-1] + 10))
w = w[ind]

def load_flux(temp,logg):
    fname="HiResFITS/PHOENIX-ACES-AGSS-COND-2011/Z-0.0/lte{temp:0>5.0f}-{logg:.2f}-0.0.PHOENIX-ACES-AGSS-COND-2011-HiRes.fits".format(temp=temp,logg=logg)
    flux_file = pf.open(fname)
    f_pure = flux_file[0].data
    flux_file.close()
    f_pure = f_pure[ind]
    print("Loaded " + fname)
    return f_pure/f_pure[0]

##################################################
#Stellar Broadening
##################################################

def karray(center, width, res):
    '''Creates a kernel array with an odd number of elements, the central element centered at `center` and spanning out to +/- width in steps of resolution. Works similar to arange in that it may or may not get all the way to the edge.'''
    neg = np.arange(center - res, center-width, -res)[::-1]
    pos = np.arange(center, center+width, res)
    kar = np.concatenate([neg,pos])
    return kar

@np.vectorize
def vsini_ang(lam0,vsini,dlam=0.01,epsilon=0.6):
    '''vsini in km/s. Epsilon is the limb-darkening coefficient, typically 0.6. Formulation uses Eqn 18.14 from Gray, The Observation and Analysis of Stellar Photospheres, 3rd Edition.'''
    lamL = vsini * 1e13 * lam0/c_ang
    lam = karray(0,lamL, dlam)
    c1 = 2.*(1-epsilon)/(np.pi * lamL * (1 - epsilon/3.))
    c2 = epsilon/(2. * lamL * (1 - epsilon/3.))
    series = c1 * np.sqrt(1. - (lam/lamL)**2) + c2 * (1. - (lam/lamL)**2)**2
    return series/np.sum(series)


##################################################
#Radial Velocity Shift
##################################################
@np.vectorize
def shift_vz(lam_source, vz):
    '''Given the source wavelength, lam_sounce, return the observed wavelength based upon a radial velocity vz in km/s. Negative velocities are towards the observer (blueshift).'''
    lam_observe = lam_source * np.sqrt((c_kms + vz)/(c_kms - vz))
    return lam_observe


##################################################
#TRES Instrument Broadening
##################################################
@np.vectorize
def gauss_kernel(dlam,V=6.8,lam0=6500.):
    '''V is the FWHM in km/s. lam0 is the central wavelength in A'''
    sigma = V/2.355 * 1e13 #A/s
    return c_ang/lam0 * 1/(sigma * np.sqrt(2*np.pi)) * np.exp( - (c_ang*dlam/lam0)**2/(2. * sigma**2))

def gauss_series(dlam,V=6.5,lam0=6500.):
    '''sampled from +/- 3sigma at dlam. V is the FWHM in km/s'''
    sigma_l = V/(2.355 * 3e5) * 6500. #A
    wl = karray(0., 4*sigma_l,dlam)
    gk = gauss_kernel(wl)
    return gk/np.sum(gk)


##################################################
#Downsample to TRES bins 
##################################################


def downsample(w_m,f_m,w_TRES):
    '''Given a model wavelength and flux (w_m, f_m) and the instrument wavelength (w_TRES), downsample the model to exactly match the TRES wavelength bins. '''
    spec_interp = interp1d(w_m,f_m,kind="linear")

    @np.vectorize
    def avg_bin(bin0,bin1):
        mdl_ind = (w_m > bin0) & (w_m < bin1)
        wave = np.empty((np.sum(mdl_ind)+2,))
        flux = np.empty((np.sum(mdl_ind)+2,))
        wave[0] = bin0
        wave[-1] = bin1
        flux[0] = spec_interp(bin0)
        flux[-1] = spec_interp(bin1)
        wave[1:-1] = w_m[mdl_ind]
        flux[1:-1] = f_m[mdl_ind]
        return trapz(flux,wave)/(bin1-bin0)

    #Determine the bin edges
    edges = np.empty((len(w_TRES)+1,))
    difs = np.diff(w_TRES)/2.
    edges[1:-1] = w_TRES[:-1] + difs
    edges[0] = w_TRES[0] - difs[0]
    edges[-1] = w_TRES[-1] + difs[-1]
    b0s = edges[:-1]
    b1s = edges[1:]

    samp = avg_bin(b0s,b1s)
    return(samp)

##################################################
#Plotting Checks
##################################################

def plot_check():
    ys = np.ones((11,))
    plt.plot(wl[-10:],ys[-10:],"o")
    plt.plot(edges[-11:],ys,"o")
    plt.show()

def compare_sample():
    fig, ax = plt.subplots(nrows=2,sharex=True,figsize=(11,8))

    ax[0].plot(wl,fl)
    ax[0].set_title("GW Ori normalized, order 23")
    
    v_shift = -30.
    Mg_shift = shift_vz(Mg,v_shift)
    f1 = model(5700,v_shift)
    ax[1].plot(wl,f1)
    ax[1].set_title("PHOENIX T=5700 K")

    ax[-1].set_xlabel(r"$\lambda\quad[\AA]$")
    ax[-1].xaxis.set_major_formatter(FSF("%.0f"))
    fig.subplots_adjust(top=0.97,right=0.97,hspace=0.25,left=0.08)
    for i in ax:
        for j in Mg_shift:
            i.axvline(j,ls=":",color="k")
    plt.show()


def compare_kurucz():
    wl,fl = np.loadtxt("kurucz.txt",unpack=True)
    wl = 10.**wl
    fig, ax = plt.subplots(nrows=4,sharex=True,figsize=(8,8))
    ax[0].plot(wl,fl)
    ax[0].set_title("Kurucz T=5750 K, convolved to 6.5 km/s")
    ax[1].plot(w,f_TRES1)
    ax[1].set_title("PHOENIX T=5700 K, convolved 6.5 km/s")
    ax[2].plot(w,f_TRES2)
    ax[2].set_title("PHOENIX T=5800 K, convolved 6.5 km/s")
    ax[3].plot(wl_n,fl_n)
    ax[3].set_title("GW Ori normalized, order 23")
    ax[-1].xaxis.set_major_formatter(FSF("%.0f"))
    ax[-1].set_xlim(5170,5195)
    ax[-1].set_xlabel(r"$\lambda\quad[\AA]$")
    plt.show()

def model(temp, vz, vsini=40., pref=1.0, logg=4.5):#, Av, T_veil):
    '''Given parameters, return the model. `temp` is effective temperature of photosphere. vsini in km/s. vz is radial velocity, negative values imply blueshift.'''
    f = load_flux(temp,logg)

    #convolve with stellar broadening (sb)
    k = vsini_ang(np.mean(wl),vsini)
    f_sb = convolve(f, k)

    wvz = shift_vz(w,vz) #shifted wavelengths

    dlam = wvz[1] - wvz[0]
    #convolve with filter to resolution of TRES
    filt = gauss_series(dlam,lam0=np.mean(wvz))
    f_TRES = convolve(f_sb,filt)

    #downsample to TRES bins,multiply by prefactor
    dsamp = downsample(wvz, f_TRES, wl)
    return pref*dsamp
    

def chi2(temp, vz, pref=1., vsini=40., logg=4.5):
    f = model(temp, vz, vsini, pref, logg)
    sigma = 0.02
    val = np.sum((fl - f)**2/sigma**2)
    return(val)

def chiMC(p):
    chi = chi2(*tuple(p))
    print(chi)
    return chi


def r(p_cur, p_old):
    return np.exp(-(chiMC(p_cur) - chiMC(p_old))/2.)

#def posterior(p):
#    return likelihood(p)*prior(p)
#
#def r(p_cur,p_old):
#    return posterior(p_cur)/posterior(p_old)

global p_old
p_old = np.array([5700,-30,1.0])

def run_chain():
    sequences = []
    for j in range(10):
        print(j)
        global p_old
        accept = False
        p_jump = np.array([np.random.choice([-300,-200,-100,0,100,200,300],p=np.array([ 0.00442619, 0.0539536, 0.24179206, 0.3996563, 0.24179206, 0.0539536, 0.00442619])),
            np.random.normal(scale=0.3), 
            np.random.normal(scale=0.01)])

        p_new = p_old + p_jump
        ratio = r(p_new, p_old)
        print("Ratio ",ratio)
        if ratio >= 1.0:
            p_old = p_new
            accept = True
        else:
            u = np.random.uniform()
            if ratio >= u:
                p_old = p_new
                accept = True
        temp,vz,pref = p_old
        sequences.append([j,ratio,accept,temp,vz,pref])

    asciitable.write(sequences,"run_0.dat",names=["j","ratio","accept","temp","vz","pref"])



def main():
    #compare_sample()
    #run_chain()
    print(chiMC((5700,-30.,1)))
    print(chiMC((5800,-30.,1)))

    pass

if __name__=="__main__":
    main()