import math

from worker import Worker
from logzero import logger
from statisticsUtils import meanAndDeviation, standardDeviationAngles, weightedMeanPairsWithDiscard
from cv2Matcher import calculateMatches

ACCEPTANCE = 1 # Value that increases the power in the score calculation. Higher acceptance means values with a higher deviation get a higher score
REJECTION = 1 # Value that increases the denomination in the score calculation. Higher rejection means values with a higher deviation get a lower score
DISTANCE_DEV_SCALE = 0.1 # Value that scales the deviation of the distance. Corrects the deviation to be more in line with the deviation of the angle
ANGLE_DEV_SCALE = 10 # Value that scales the deviation of the angle. Corrects the deviation to be more in line with the deviation of the distance
DISCARD_PERCENTILE = 20 # Percentile of values to discard when calculating the weighted mean

class SpeedWorker(Worker):
    """Worker that calculates the speed from a queue of `ImagePairs`"""
    def __init__(self, gsd):
        """Initializes the worker with a specified Ground Sample Distance (gsd)"""
        super().__init__()
        self.gsd = gsd
        self._Worker__value = 0

    def calculateScore(self, d0, d1):
        """Calculate the score from two deviations. """
        m = REJECTION ** ACCEPTANCE
        return 1/(m*(d0**2+d1**2)**ACCEPTANCE+1)

    def calculateSpeedFromMatches(self, match_data, gsd):
        """Returns the speed and score from a set of matches and a specified Ground Sample Distance (gsd)"""
        coords1 = match_data.coordinates_1
        coords2 = match_data.coordinates_2
        if len(coords1) == 0:
            return (0,0)
        
        distances = []
        angles = []
        # iterate through matches and get gradient and distance
        for i in range(0, len(coords1)):
            x1 = coords1[i][0]
            y1 = coords1[i][1]
            x2 = coords2[i][0]
            y2 = coords2[i][1]
            distance = math.sqrt((x2-x1)**2 + (y2-y1)**2)*gsd
            distances.append(distance)
            angle = math.atan2((y2-y1),(x2-x1))
            angles.append(angle)

        # calculate the average distance and angle
        meanDistance, devDistance = meanAndDeviation(distances)
        devDistance*=DISTANCE_DEV_SCALE
        devAngle = standardDeviationAngles(angles)
        devAngle*=ANGLE_DEV_SCALE
        score = self.calculateScore(devDistance, devAngle)

        return (meanDistance, score)

    def work(self):
        """While not cancelled, calculate and refine a value for speed using the queue of `ImagePairs`"""
        speedScorePairs = []
        while not self.cancelled:  # loop until cancelled
            try:
                if not self.queue.empty():
                    # get pair and compute matches
                    imagePair = self.queue.get(False)
                    matchData = calculateMatches(imagePair)
                    # calculate speed score and append to list
                    distance, score = self.calculateSpeedFromMatches(matchData, self.gsd)
                    speed = distance/imagePair.timeDifference
                    speedScorePairs.append((speed, score))

                    newSpeed = weightedMeanPairsWithDiscard(speedScorePairs, DISCARD_PERCENTILE)
                    logger.info(f"Calculated Speed: {speed}, {score}. Average Speed: {newSpeed}")
                    self._Worker__value = newSpeed    
            except Exception as e:
                logger.error(e)
        self.cancel() # ensure the worker is marked as cancelled when the loop ends
