import numpy as np
import log_reader as lr
import tracking_reader as tr
from filterpy.kalman import UnscentedKalmanFilter as UKF
import mpl_toolkits.mplot3d as m3d
import matplotlib.pyplot as plt

START_TIME = 254000 # ms
END_TIME = 268241 # ms
dt = 1000.0/30 # ms
fx_times = 1
cum_x = np.zeros(12)
t = START_TIME

def get_R(att):
    #att = np.deg2rad(att)
    r_pitch = np.array([[ np.cos(att[1]), 0, -np.sin(att[1])],
                        [              0, 1,               0],
                        [ np.sin(att[1]), 0,  np.cos(att[1])]])
    r_roll = np.array([[1,               0,              0],
                       [0,  np.cos(att[0]), np.sin(att[0])],
                       [0, -np.sin(att[0]), np.cos(att[0])]])
    r_yaw = np.array([[ np.cos(att[2]), np.sin(att[2]), 0],
                      [ -np.sin(att[2]), np.cos(att[2]), 0],
                      [              0,              0, 1]])
    R = r_roll.dot(r_pitch.dot(r_yaw))
    return R

def hx(x):
	"""
	return the measurement of the state
	"""
	C = np.eye(12)
	"""
	C[9, 9] = 0
	C[9, 0] = 1
	C[10, 10] = 0
	C[10, 1] = 1
	C[11, 11] = 0
	C[1, 2] = 1
	"""
	V = np.vstack((C,C[0:3:]))
	return V.dot(x)

def fx(x, dt):
	"""
	return the state transformed by the state transition function
	dt is in seconds
	"""
	global left_reader
	global t
	m = 2.9 # mass in kg
	l = .1516 # length of quadcopter rotor in
	w = .2357
	I_x = .3789
	I_y = .06193
	k_i_2 = .00009876
	k1 = .0092
	g = 9.8

	dt_ms = dt * 1000
	mi = left_reader.get_motor_vals(t)
	mi = mi - 1143 # important
	R = get_R([x[6], x[7], x[8]])
	R_inv = np.linalg.inv(R)

	F = mi.sum() *k1


	pos_dots = R_inv.dot(np.array([x[3], x[4], x[5]])) # x_dot, y_dot, z_dot
	
	u_dot = -g * np.sin(x[7])
	v_dot = g * np.cos(x[7]) * np.sin(x[6]) 
	w_dot = g * np.cos(x[7]) * np.cos(x[6]) - (F/m)

	R_att = np.array([[1, np.sin(x[6])*np.tan(x[7]), np.cos(x[6])*np.tan(x[7])],
					  [0, np.cos(x[6]), -np.sin(x[6])],
					  [0, np.sin(x[6])*(1.0/np.cos(x[7])), np.cos(x[6])*(1.0/np.cos(x[7]))]])

	att_dots = R_att.dot(np.array([x[9], x[10], x[11]]))

	# torque around phi
	t_phi = np.array([-w*k1, w*k1, -w*k1, w*k1, -w*k1, w*k1, -w*k1, w*k1]).dot(mi)
	t_theta = np.array([l*k1, l*k1, -l*k1, -l*k1, l*k1, l*k1, -l*k1, -l*k1]).dot(mi)
	t_psi = np.array([k_i_2, -k_i_2, -k_i_2, k_i_2, -k_i_2, k_i_2, k_i_2, -k_i_2]).dot(mi)

	r_dot = t_psi
	p_dot = t_phi/I_x
	q_dot = t_theta/I_y

	state_dot = np.array([pos_dots[0], pos_dots[1], pos_dots[2], u_dot, v_dot, w_dot, att_dots[0], att_dots[1], att_dots[2], p_dot, q_dot, r_dot])

	new_state = x + state_dot*dt

	return new_state

"""
Log stuff
"""
vid_fname = "c:\\Users\\Joseph\\Documents\\14-15\\Thesis\\SeniorThesis2015\\ball_tracker\\svm\\videos\\output.mp4"

l_fname = "c:\\Users\\Joseph\Videos\\Flight With Ball\\Left.MP4"
l_logname = "c:\\Users\\Joseph\Videos\\Flight With Ball\\Left.log"
l_rect_start_time_ms = 259000
l_first_data_time_ms = 14414.4

stereo_offset = (14481.133 - 14414.4)

r_fname = "c:\\Users\\Joseph\Videos\\Flight With Ball\\Right.MP4"
r_logname = "c:\\Users\\Joseph\Videos\\Flight With Ball\\Right.log"
r_rect_start_time_ms = l_rect_start_time_ms + int(stereo_offset)
r_first_data_time_ms = 31064.366

C920_data = np.load("C920_calib_data.npz")
F = C920_data['intrinsic_matrix']
track_fname = "super_ball_track.log"
track_offset = 30230   #tracking log is ~29998 ms behind left gopro
track_data_log_offset = track_offset + stereo_offset

left_reader = lr.LogReader(l_logname,l_first_data_time_ms)
right_reader = lr.LogReader(r_logname,r_first_data_time_ms)

track = tr.TrackingReader(track_fname,right_reader,track_data_log_offset,F,30,1,vid_fname=vid_fname)

pos_init = left_reader.get_ekf_loc_1d(START_TIME)
vel_init = left_reader.get_ekf_vel(START_TIME)
att_init = np.deg2rad(left_reader.get_ekf_att(START_TIME))
att_vel_init = np.zeros(3)
state_init = np.hstack((pos_init,vel_init,att_init,att_vel_init))

ukf = UKF(dim_x=12, dim_z=15, dt=1.0/30, fx=fx, hx=hx)
ukf.P = np.diag([5,5,2, 2,2,2, .017,.017,.017, .1,.1,.1])
ukf.x = state_init
ukf.Q = np.diag([.5,.5,.5, .5,.5,.5, .1,.1,.1, .1,.1,.1])

T = np.array([16.878, -7.1368, 0])		#Translation vector joining two inertial frames
time = np.arange(START_TIME,END_TIME,dt)
print time.shape,time[0],time[-1]
d = np.linspace(20,40,time.shape[0])
zs = np.zeros((time.shape[0],15))
Rs = np.zeros((time.shape[0],15,15))

means = np.zeros((time.shape[0],12))
covs = np.zeros((time.shape[0],12,12))
cam_locs = np.zeros((time.shape[0],3))
ekf_locs = np.zeros((time.shape[0],3))

for i in range(1,time.shape[0]):
	t = time[i]
	
	ukf.predict(1.0/30)
	# Get camera location and covariance points in ball inertial frame
	cam_loc = track.get_mean(t,d[i]) + T
	cam_sigs = track.get_cov(t,d[i],10) + T[:,None]
	cam_points = np.vstack((cam_sigs.T, cam_loc)).T
	cam_cov = np.cov(cam_points)
	
	# Get kalman filter state estimate
	ekf_loc = left_reader.get_ekf_loc_1d(t)
	ekf_vel = left_reader.get_ekf_vel(t)
	ekf_att = np.deg2rad(left_reader.get_ekf_att(t))
	ekf_attdot = np.deg2rad(left_reader.get_gyr(t))
	
	ekf_locs[i,:] = ekf_loc
	cam_locs[i,:] = cam_loc
	
	z = np.hstack((ekf_loc,ekf_vel,ekf_att,ekf_attdot,cam_loc))
	zs[i,:] = z
	
	R = np.array([[5,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
				  [0,5,0,0,0,0,0,0,0,0,0,0,0,0,0],
				  [0,0,2,0,0,0,0,0,0,0,0,0,0,0,0],
				  [0,0,0,2,0,0,0,0,0,0,0,0,0,0,0],
				  [0,0,0,0,2,0,0,0,0,0,0,0,0,0,0],
				  [0,0,0,0,0,2,0,0,0,0,0,0,0,0,0],
				  [0,0,0,0,0,0,.017,0,0,0,0,0,0,0,0],
				  [0,0,0,0,0,0,0,.017,0,0,0,0,0,0,0],
				  [0,0,0,0,0,0,0,0,.017,0,0,0,0,0,0],
				  [0,0,0,0,0,0,0,0,0,0.1,0,0,0,0,0],
				  [0,0,0,0,0,0,0,0,0,0,0.1,0,0,0,0],
				  [0,0,0,0,0,0,0,0,0,0,0,0.1,0,0,0],
				  [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
				  [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
				  [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]]).astype(float)
	R[12:15,12:15] = cam_cov
	Rs[i,:,:] = R
	
	ukf.update(z,R)
	means[i,:] = ukf.x
	
	print means[i,:]
	covs[i,:,:] = ukf.P

locs = means[:,0:3]
print locs.shape

ax = m3d.Axes3D(plt.figure(2))
ax.scatter3D(*locs.T,c='r')
ax.scatter3D(*cam_locs.T,c='g')
ax.scatter3D(*ekf_locs.T,c='b')

ax.set_xlim3d(-25,25)
ax.set_ylim3d(-25,25)
ax.set_zlim3d(-50,0)
plt.show()
#means, covs = ukf.batch_filter(zs,Rs)
#print means.shape, covs.shape

np.save("cum_x.npy", cum_x)	