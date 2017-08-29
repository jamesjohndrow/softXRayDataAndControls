import pyca
from donemoving import donemoving
import sys
import time
from caget import caget
from math import fabs
from Pv import Pv
#from smartMotor import SmartMotor

class AScan:
    def __init__(self, motor, pos1, pos2, num_intervals, return_after=True):
        self._motor = motor
        self.__init_pos = motor.get_position()
        self.__pos1 = pos1
        self.__pos2 = pos2
        self.__num_intervals = num_intervals
        self.__return_after = return_after
        self._delta = float(pos2 - pos1) / num_intervals
        self._nstep = 0
        self.__success = True
        self.__total_steps = num_intervals + 1
        self._pre_scan_hook = self.__no_op
        self._pre_move_hook = self.__no_op
        self._post_move_hook = self.__no_op
        self._post_scan_hook = self.__no_op
        
        self.__validate()
        
        pass

    def __validate(self):       
        ok = True
        if not self._motor.is_in_range(self.__pos1):
            ok = False
            print "ERROR: %s" % (self._motor.why_outside_range(self.__pos1))
            pass
        if not self._motor.is_in_range(self.__pos2):
            ok = False
            print "ERROR: %s" % (self._motor.why_outside_range(self.__pos2))
            pass

        if not ok:
            raise Exception("Scan parameters Invalid")
            
        pass

    def __no_op(self, scan):
        pass

    def get_success(self):
        return self.__success

    def get_position(self):
        return self._motor.get_position()

    def get_initial_position(self):
        return self.__init_pos

    def get_step(self):
        return self._nstep

    def get_delta(self):
        return self.__delta

    def get_total_steps(self):
        return self.__total_steps

    def get_return_after(self):
        return self.__return_after

    # will pass pos1, pos2, nIntervals to this method
    def set_pre_scan_hook(self, hook):
        self._pre_scan_hook = hook
        pass

    # will pass next commanded position to this hook
    def set_pre_move_hook(self, hook):
        self._pre_move_hook = hook
        pass

    # will pass current position to this hook
    def set_post_move_hook(self, hook):
        self._post_move_hook = hook
        pass

    # will pass boolean flag to this hook to tell if scan succeeded
    def set_post_scan_hook(self, hook):
        self._post_scan_hook = hook
        pass

    def get_pos1(self):
        return self.__pos1
        
    def get_pos2(self):
        return self.__pos2

    def get_num_intervals(self):
        return self.__num_intervals

    def _check_limits(self):
        lim_status = self._motor.checkLimits()
        if (lim_status == 0):
            return
        else:
            if (lim_status < 0):
                raise Exception("Low limit switch tripped on '%s'! Scan stopped after %u intervals." % (self._motor.motor_name, self._nstep))
            elif (lim_status > 0):
                raise Exception("High limit switch tripped on '%s'! Scan stopped after %u intervals." % (self._motor.motor_name, self._nstep))
            pass
        pass
                                    
    
    def go(self):
        hasMoved = False
        self._nstep = 0
        nextpos = self.get_pos1()
        print "Beginning Scan"
        try:

            self._pre_scan_hook(self)

            for step in range(0, self.get_total_steps()):
                self._nstep+=1
                self._pre_move_hook(self)
                self._motor.move_wait(nextpos)
                self._post_move_hook(self)
                self._check_limits()
                nextpos += self._delta
                pass

        except Exception, e:
            success = False
            print "ERROR: %s" % e.message
            raise e
        
        finally:
            if (self.__return_after):
                print "Returning motor(s) to original position..."
                self._motor.move_wait(self.__init_pos)
                print "Done."
                # TODO: Tell hook if scan succeeded.
            self._post_scan_hook(self)
            pass
        
        pass
    pass



class DScan(AScan):
    def __init__(self, motor, rel1, rel2, num_intervals, return_after=True):
        AScan.__init__(self,
                       motor,
                       motor.get_position() + rel1,
                       motor.get_position() + rel2,
                       num_intervals,
                       return_after
                       )
        pass

    pass


class A2Scan(AScan):
    def __init__(self,
                 motor1,
                 motor1_pos1,
                 motor1_pos2,
                 motor1_num_intervals,
                 motor2,
                 motor2_pos1,
                 motor2_pos2,
                 motor2_num_intervals,
                 return_after=True
                 ):
        
        
        AScan.__init__(self,
                       motor1,
                       motor1_pos1,
                       motor1_pos2,
                       motor1_num_intervals,
                       return_after
                       )
        
        self.__inner_motor = motor2

        self.__inner_scan = AScan(motor2,
                                  motor2_pos1,
                                  motor2_pos2,
                                  motor2_num_intervals,
                                  False
                                  )
#        self.__inner_scan.set_post_move_hook(self.__after_inner_move)
        pass

    def set_pre_move_hook(self, hook):
        self.__inner_scan._pre_move_hook = hook
        pass

    def set_post_move_hook(self, hook):
        self.__inner_scan._post_move_hook = hook
        pass

    
    
    def go(self):
        hasMoved = False
        self._nstep = 0
        nextpos = self.get_pos1()
        print "Beginning Scan"
        try:

            self._pre_scan_hook(self)

            for step in range(0, self.get_total_steps()):
                self._nstep+=1
                self._pre_move_hook(self)
                self._motor.move(nextpos)
                self.__inner_motor.move_wait(self.__inner_scan.get_pos1())
                self._motor.wait()
                
                self.__inner_scan.go()
                self._post_move_hook(self)
                self._check_limits()
                nextpos += self._delta
                pass

        except Exception, e:
            success = False
            print "ERROR: %s" % e
            raise e
                    
        finally:
            if (self.get_return_after()):
                print "Returning motors to original position"
                sys.stdout.flush()
                self._motor.move(self.get_initial_position())
                self.__inner_motor.move_wait(self.__inner_scan.get_initial_position())
                self._motor.wait()
            self._post_scan_hook(self)
            pass
        
        pass
    
    # TODO: REMOVE THIS -- For testing, this prints the position
    def __after_inner_move(self, scan):
        print "position: %6.3f\t%6.3f" % (self.get_position(), scan.get_position())
        pass

    pass


# This D2Scan class doesn't work well at all.  It gets really messed up and screws up other things.
class D2Scan(A2Scan):
    def __init__(self,
                 motor1,
                 motor1_rel1,
                 motor1_rel2,
                 motor1_num_intervals,
                 motor2,
                 motor2_rel1,
                 motor2_rel2,
                 motor2_num_intervals,
                 return_after=True
                 ):
        
        A2Scan.__init__(self,
                        motor1,
                        motor1.get_position() + motor1_rel1,
                        motor1.get_position() + motor1_rel2,
                        motor1_num_intervals,
                        motor2,
                        motor2.get_position() + motor2_rel1,
                        motor2.get_position() + motor2_rel2,
                        motor2_num_intervals,
                        return_after=True
                        )
        pass
    pass
