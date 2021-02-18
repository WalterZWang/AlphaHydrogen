import pandas as pd
import numpy as np
from datetime import datetime


class dataFromCSV():

    def __init__(self, csv_file, stepLenth):
        '''Input csv file needs to be hourly load 
        '''
        self.csv_file = csv_file
        self.load = pd.read_csv(self.csv_file, index_col=0)
        ## Check the input load
        assert self.load.shape[0] == 8760, "Input building load file needs to be hourly."
        if self.load.shape[1] > 1:
            print('Input building load file have more than 1 column, only the first column will be used.')
        self.stepLenth = stepLenth  #unit: s
        self.setTimeStep()

    def setTimeStep(self):
        start_time = datetime(year = 2019, month = 1, day =1)
        self.load.index = pd.date_range(start_time, periods = self.load.shape[0], freq = 'H')
        self.load = self.load.resample('{}T'.format(self.stepLenth/60)).interpolate()



class Building(dataFromCSV):

    def __init__(self, csv_file, stepLenth):
        super().__init__(csv_file, stepLenth)

    def getLoad(self, timeStep):
        '''Time step start with 0
        '''
        return self.load.iloc[timeStep, 0]
    
    def getLoadFullYear(self):
        return self.load


class PV(dataFromCSV):

    def __init__(self, csv_file, stepLenth):
        super().__init__(csv_file, stepLenth)

    def getPower(self, timeStep):
        '''Time step start with 0
        '''
        return self.load.iloc[timeStep, 0]

    def getPowerFullYear(self):
        return self.load

class Vehicle:

    def __init__(self, csv_file, schd_file, fuelCell, stepLenth):
        '''Class of vehicle, equiped with a H2 tank and fuelCell
        Consume H2 for daily communiting
        Can be charged through the H2 station
        Can be discharged to the grid through fuel cell
        ------------------------------------
        Args
            -- csv_file, key parameters of the vehicle
            -- schd_file, parking schedule of the vehicle
            -- fuelCell, an instance of fuel cell
            -- stepLenth, lenth of each time step, unit: s
        ------------------------------------
        State
            -- tankVol: current storage volumn of the H2 tank
        '''
        self.vehicle_info = pd.read_csv(csv_file)
        self.vehicle_schd = pd.read_csv(schd_file)
        self.fuelEff = float(self.vehicle_info.loc[0,'fuelEff'])  # unit: g/km
        self.dist_mu_wd = float(self.vehicle_info.loc[0,'dist_mean_wd'])
        self.dist_sigma_wd = float(self.vehicle_info.loc[0,'dist_std_wd'])
        self.dist_mu_nwd = float(self.vehicle_info.loc[0,'dist_mean_nwd'])
        self.dist_sigma_nwd = float(self.vehicle_info.loc[0,'dist_std_nwd'])
        self.maxH2ChargingCapacity = float(self.vehicle_info.loc[0,'maxH2ChargingCapacity'])
        self.tankCapacity = float(self.vehicle_info.loc[0,'tankCapacity'])          # unit: g
        self.parkSchd_wd = self.vehicle_schd[self.vehicle_info.loc[0,'parkSchd_wd']]
        self.parkSchd_nwd = self.vehicle_schd[self.vehicle_info.loc[0,'parkSchd_nwd']]
        self.fuelCell = fuelCell
        self.stepLenth = stepLenth                # unit: s
        # Initialize H2 storage in the tank
        self.tankVol = 0                          # unit: g
    
    def h2FromStation(self, chargeRate):
        '''
        ------------------------------------
        Args
            -- chargeRate, control signal for the charge rate, unit: g/s
        ------------------------------------
        Output
            -- real charge rate
        '''
        realH2ChargeRate = capacity_storage_constraint(controlSignal=chargeRate, 
                                                       maxCapacity=self.maxH2ChargingCapacity, 
                                                       maxStorage=self.tankCapacity, 
                                                       minStorage=0, 
                                                       currentStorage=self.tankVol, 
                                                       stepLenth=self.stepLenth, 
                                                       charging=True)
        realH2ChargeVol = realH2ChargeRate * self.stepLenth
        self.tankVol += realH2ChargeVol
        return realH2ChargeRate
    
    def cruise(self, workingDay):
        H2Consmption = self._getH2Consumption(workingDay)
        self.tankVol -= H2Consmption


    def eleToGrid(self, dischargePower):
        '''
        ------------------------------------
        Args
            -- dischargePower, control signal for the discharge, unit: kW
        ------------------------------------
        Output
            -- real discharge power
        '''
        fuelCellEff = self.fuelCell.getEff()                  # kJ per g H2 consumption
        fuelCellCapacity = self.fuelCell.getCapacity()        # kW
        currentStorage = self.tankVol*fuelCellEff             # unit: kJ
        realDischargePower = capacity_storage_constraint(controlSignal=dischargePower, 
                                                         maxCapacity=fuelCellCapacity, 
                                                         maxStorage=float('inf'), 
                                                         minStorage=0, 
                                                         currentStorage=currentStorage, 
                                                         stepLenth=self.stepLenth, 
                                                         charging=False)        
        H2Consumption = (realDischargePower*self.stepLenth)/fuelCellEff   # Unit: g
        self.tankVol -= H2Consumption                # unit: g
        return realDischargePower

    def _getH2Consumption(self, workingDay):
        distance = self._getDistance(workingDay)
        H2Consmption = self.fuelEff*distance         # unit: g
        return H2Consmption
    
    def _getDistance(self, workingDay):
        if workingDay:
            self.distance = np.random.normal(self.dist_mu_wd, self.dist_sigma_wd, 1)[0]
        else:
            self.distance = np.random.normal(self.dist_mu_nwd, self.dist_sigma_nwd, 1)[0]
        return self.distance

    def getParkSchd(self, workingDay):
        self.parkSchd = self.parkSchd_wd if workingDay else self.parkSchd_nwd
        return self.parkSchd
    

class H2Station:

    def __init__(self, pipeChargingCapacity, vehicleDischargingCapacity, storageCapacity, electrolyzer, stepLenth):
        '''Class of H2 station, equiped with a H2 tank and electrolyzer
        Can be charged through the pipe or the grid (through electrolyzer)
        Can be discharged to the vehicle
        ------------------------------------
        Args
            -- pipeChargingCapacity, pipe maximum charging capacity, unit: g/s
            -- vehicleDischargingCapacity, maximum discharging capacity to vehicle, unit: g/s
            -- storageCapacity, maximum H2 storage capacity, unit: g
            -- electrolyzer, an instance of electrolyzer
            -- stepLenth, lenth of each time step, unit: s
        ------------------------------------
        State
            -- tankVol: current storage volumn of the H2 tank
        '''
        self.pipeChargingCapacity = pipeChargingCapacity
        self.vehicleDischargingCapacity = vehicleDischargingCapacity 
        self.tankCapacity = storageCapacity
        self.electrolyzer = electrolyzer
        self.stepLenth = stepLenth
        self.tankVol = 0
    
    def h2Charge(self, chargePowerFromGrid, chargeRateFromPipe):
        '''Charge station H2 tank from either H2 pipe or from grid through electrolyzer
        If reaching the maximum charging or storage capacity, charging from the grid has is prioritized
        ------------------------------------
        Args
            -- chargePowerFromGrid, control signal of H2 charging from Grid through electrolyzer, unit: kW
            -- chargeRateFromPipe, control signal of H2 charging from H2 pipe, unit: unit g/s
        ------------------------------------
        Output
            -- realChargePowerFromGrid: unit kW 
            -- realChargeRateFromGrid: unit g/s
        '''
        ## charge the tank using the electrolyzer first
        electrolyzerCapacity = self.electrolyzer.getCapacity()
        electrolyzerEff = self.electrolyzer.getEff()                  # g/(kW*s)
        chargeRateFromGrid = chargePowerFromGrid*electrolyzerEff      # g/s
        realChargeRateFromGrid = capacity_storage_constraint(controlSignal=chargeRateFromGrid, 
                                                            maxCapacity=electrolyzerCapacity, 
                                                            maxStorage=self.tankCapacity, 
                                                            minStorage=0, 
                                                            currentStorage=self.tankVol, 
                                                            stepLenth=self.stepLenth, 
                                                            charging=True)    
        realChargePowerFromGrid = realChargeRateFromGrid/electrolyzerEff   # kW
        # charge the tank using the pipe
        realChargeRateFromPipe = capacity_storage_constraint(controlSignal=chargeRateFromPipe, 
                                                            maxCapacity=self.pipeChargingCapacity, 
                                                            maxStorage=self.tankCapacity, 
                                                            minStorage=0, 
                                                            currentStorage=self.tankVol+realChargeRateFromGrid*self.stepLenth, 
                                                            stepLenth=self.stepLenth, 
                                                            charging=True)       

        self.tankVol += (realChargeRateFromGrid+realChargeRateFromPipe)*self.stepLenth
        return realChargePowerFromGrid, realChargeRateFromPipe

    def h2ToVehicle(self, chargeRates):
        '''Discharge the station to fill in the vehicle H2 tank
        If reaching the maximum discharge rate, charge the vehicles with the lowest index in the numpy array
        ------------------------------------
        Input
            -- chargeRates, nump array of dischargeRate for each vehivle, unit g/s
        ------------------------------------
        Output
            -- realChargeRates, nump array of dischargeRate for each vehivle, unit g/s
        '''
        # Satify the maximum charging capacity 
        realDischargeRate = capacity_storage_constraint(controlSignal=np.sum(chargeRates), 
                                                     maxCapacity=self.vehicleDischargingCapacity, 
                                                     maxStorage=self.tankCapacity, 
                                                     minStorage=0, 
                                                     currentStorage=self.tankVol, 
                                                     stepLenth=self.stepLenth, 
                                                     charging=False) 
        cumSum = np.cumsum(chargeRates)
        max_charging_num = (cumSum<realDischargeRate).sum()
        realChargeRates = chargeRates.copy()
        realChargeRates[max_charging_num:] = 0
        realChargeVol = realChargeRates.sum()*self.stepLenth
        self.tankVol -= realChargeVol
        return realChargeRates


def capacity_storage_constraint(controlSignal, maxCapacity, maxStorage, minStorage, currentStorage, stepLenth, charging):
    '''Return the real output based on the capacity and storage constraint
    ----------------------------------------------------------------------
    Args:
        -- controlSignal: control signal input, must be positive, unit []/s, example kW for charging 
        -- maxCapacity: maximum charging/discharging capacity, unit []/s, example: kW for charging capacity
        -- maxStorage: maximum storage capacity, unit [], example: kg for H2 storage
        -- currentStorage: current storage, unit [], example: kg for H2 storage 
        -- stepLenth: length of each simulation time step, example: 300 s
        -- charging: binary variable, True for charging, False for discharging
    Output:
        -- Actual output satisfying all the constraints, Unit: []/h 
    '''
    capacityConstraint = maxCapacity
    if charging:
        storageConstraint = (maxStorage-currentStorage)/stepLenth
    else:
        storageConstraint = (currentStorage-minStorage)/stepLenth
    realOutput = min(controlSignal, capacityConstraint, storageConstraint)
    return realOutput

# class Grid:

#     def __init__():



# class OfflineRenewable:

#     def __init__(self):





class FuelCell:

    def __init__(self, efficiency, capacity):
        '''Fuel cell, convert H2 to electricity
        ----------------------------------------------------------------------
        Args:
            -- efficiency: unit kJ per g H2 consumption
            -- capacity: maximum capacity, unit kW
        ----------------------------------------------------------------------
        State:
            None
        '''
        self.efficiency = efficiency
        self.fuelCellCapacity = capacity

    
    def getEff(self):
        '''Retunr the efficiency of the fuel cell
        -------------------------------------
        Input

        -------------------------------------
        Output
            -- Unit: kJ per g H2 consumption
        '''

        return self.efficiency

    def getCapacity(self):
        '''Retunr the maximum capacity of the fuel cell
        -------------------------------------
        Args

        -------------------------------------
        Output
            -- Unit: kW
        '''

        return self.fuelCellCapacity

class Electrolyzer():

    def __init__(self, efficiency, capacity):
        '''Electrolyzer, convert electricity to H2
        ----------------------------------------------------------------------
        Args:
            -- efficiency: unit g H2 consumption per kJ
            -- capacity: maximum H2 generation capacity, unit g/s
        ----------------------------------------------------------------------
        State:
            None
        '''
        self.electrolyzerEff = efficiency        
        self.electrolyzerCapacity = capacity

    def getEff(self):
        '''Retunr the efficiency of the fuel cell
        -------------------------------------
        Input

        -------------------------------------
        Output
            -- Unit: g H2 consumption per kJ
        '''

        return self.electrolyzerEff

    def getCapacity(self):
        '''Retunr the maximum capacity of the electrolyzerCapacity
        -------------------------------------
        Args

        -------------------------------------
        Output
            -- Unit: g/s H2
        '''

        return self.electrolyzerCapacity

# if __name__ == "__main__":

