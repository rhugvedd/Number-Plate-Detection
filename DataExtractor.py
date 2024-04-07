import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image
import pandas as pd
from sklearn.cluster import KMeans
import time
from datetime import datetime

class DataExtractor(nn.Module):
    def __init__(
                    self,
                    data_path,
                    save_path,
                    annotations_csv,
                    scaled_image_size: tuple,
                    anchor_nos: int,
                    scaling_fact: int,
                    device,
                    anchor_boxes: list = None
                ):
        super(DataExtractor, self).__init__()
    
        self.data_path = data_path
        self.save_path = save_path
        self.annotations_csv = annotations_csv
        self.scaled_image_size = scaled_image_size
        self.scaling_fact = scaling_fact
        self.final_grid_size = (scaled_image_size[0] // self.scaling_fact, scaled_image_size[1] // self.scaling_fact)
        
        if(anchor_boxes != None):
            self.anchor_nos = len(anchor_boxes)
        else:
            self.anchor_nos = anchor_nos

        self.to(device)
    
    def extractXY_toMem(self, X_Name, Y_Name, Anchor_name, print_interval, num_examples = None):
        StTime = time.time()
        print("Extraction Started:")
        
        transform = transforms.Compose([
            transforms.Resize(self.scaled_image_size),
            transforms.ToTensor()
        ])
        
        image_names, bounding_boxes = self.get_bounding_boxes(num_examples)
        
        X_train = torch.zeros   (
                                    image_names.shape[0], 
                                    3, 
                                    self.scaled_image_size[0], 
                                    self.scaled_image_size[1], 
                                    dtype=torch.float16
                                )

        Y_train = torch.zeros   (
                                    bounding_boxes.shape[0], 
                                    self.final_grid_size[0], 
                                    self.final_grid_size[1], 
                                    self.anchor_nos * 5, 
                                    dtype=torch.float16
                                )

        anchors = self.getAnchors_fromMem(Anchor_name)

        for idx, image_name, box in zip(range(image_names.shape[0]), image_names, bounding_boxes):

            image = Image.open(self.data_path + image_name).convert("RGB")
            
            X_scale = self.scaled_image_size[0] / image.width
            Y_scale = self.scaled_image_size[1] / image.height

            image = transform(image)
            
            X_train[idx] = image

            box[0::2] = box[0::2] * X_scale
            box[1::2] = box[1::2] * Y_scale
                
            box_centre = ((box[2] + box[0]) / 2, (box[3] + box[1]) / 2)
            grid_cell = (int(box_centre[1] // self.scaling_fact), int(box_centre[0] // self.scaling_fact))
            max_iou_anchor = self.get_max_iou_anchor(box, anchors, box_centre, grid_cell)

            Temp = Y_train[idx][grid_cell[0]][grid_cell[1]][max_iou_anchor * 5]     = (box_centre[0] - (grid_cell[1] * self.scaling_fact)) / self.scaling_fact
            Temp = Y_train[idx][grid_cell[0]][grid_cell[1]][max_iou_anchor * 5 + 1] = (box_centre[1] - (grid_cell[0] * self.scaling_fact)) / self.scaling_fact
            Temp = Y_train[idx][grid_cell[0]][grid_cell[1]][max_iou_anchor * 5 + 2] = (box[2] - box[0]) / anchors[max_iou_anchor][0]
            Temp = Y_train[idx][grid_cell[0]][grid_cell[1]][max_iou_anchor * 5 + 3] = (box[3] - box[1]) / anchors[max_iou_anchor][1]
            Temp = Y_train[idx][grid_cell[0]][grid_cell[1]][max_iou_anchor * 5 + 4] = 1

            if idx % print_interval == 0: print(idx)

        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        torch.save(X_train, self.save_path + X_Name + '-' + date_time.replace(':', '-') + '.pt')
        torch.save(Y_train, self.save_path + Y_Name + '-' + date_time.replace(':', '-') + '.pt')

        print(f"Time Taken: {time.time() - StTime} s")

    def extractX_toMem(self, X_Name):
        StTime = time.time()
        print("Extraction Started:")
        
        transform = transforms.Compose([
            transforms.Resize(self.scaled_image_size),
            transforms.ToTensor()
        ])
        
        csv_file = self.data_path + self.annotations_csv

        data = pd.read_csv(csv_file, header = None)
        
        image_names = data.iloc[:, 0]
        
        X_train = torch.zeros(image_names.shape[0], 3, self.scaled_image_size[0], self.scaled_image_size[1], dtype=torch.float16)
        
        for idx, image_name in enumerate(image_names):

            image = Image.open(self.data_path + image_name).convert("RGB")
            
            image = transform(image)
            
            X_train[idhx] = image

            print(idx)

        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        torch.save(X_train, self.save_path + X_name + date_time + '.pt')

        print(f"Time Taken: {time.time() - StTime} s")

    def get_max_iou_anchor(self, box, anchors, box_centre, grid_cell):
        
        max_iou = 0
        sel_anchor = 0

        for idx, anchor in enumerate(anchors):
            ix1 = torch.max(box[0], box_centre[0] - (anchor[0] / 2))
            iy1 = torch.max(box[1], box_centre[1] - (anchor[1] / 2))
            ix2 = torch.min(box[2], box_centre[0] + (anchor[0] / 2))
            iy2 = torch.min(box[3], box_centre[1] + (anchor[1] / 2))

            inter_area = torch.max(ix2 - ix1, torch.tensor(0)) * torch.max(iy2 - iy1, torch.tensor(0))
            union_area = ((box[2] - box[0]) * (box[3] - box[1])) + (anchor[0] * anchor[1]) - inter_area
            
            iou = inter_area / union_area
            if (iou) > max_iou:
                sel_anchor = idx

                max_iou = iou

        return sel_anchor

    def get_bounding_boxes(self, num_boxes = None):
        
        csv_file = self.data_path + self.annotations_csv

        data = pd.read_csv(csv_file, header = None)

        image_names = data.iloc[:num_boxes, 0]

        return image_names, torch.tensor(data.iloc[:num_boxes, 1:].values)

    def extractAnchors_toMem(self, Anchor_name):
        StTime = time.time()

        image_names, bounding_boxes = self.get_bounding_boxes()

        for idx, image_name in enumerate(image_names):

            image = Image.open(self.data_path + image_name).convert("RGB")

            X_scale = self.scaled_image_size[0] / image.width
            Y_scale = self.scaled_image_size[1] / image.height

            box = bounding_boxes[idx]

            centre_x = ((box[0] + box[2]) / 2) * X_scale
            centre_y = ((box[1] + box[3]) / 2) * Y_scale

            width = (box[2] - box[0]) * X_scale
            height = (box[3] - box[1]) * Y_scale

            bounding_boxes[idx][0] = centre_x
            bounding_boxes[idx][1] = centre_y
            bounding_boxes[idx][2] = width
            bounding_boxes[idx][3] = height

            if idx % 100 == 0: print(idx)
            
        anchors = self.detect_anchors(bounding_boxes[:, 2:], self.anchor_nos)
        
        print(anchors)
        print(f"Time Taken: {time.time() - StTime} s")
        
        if str(input("Save? ('N' for NO)")) != 'N': 
            torch.save(anchors, self.save_path + Anchor_name + '.pt')
            print("Anchors saved succesfully!")
        else:
            print("Anchors not saved :(")
    
    def detect_anchors(self, box_dim, anchor_nos):

        kmeans = KMeans(n_clusters=anchor_nos)

        kmeans.fit(box_dim)

        cluster_centers = kmeans.cluster_centers_

        return cluster_centers
        
    def getXY_fromMem(self, X_Name, Y_name):
        return torch.load(self.save_path + X_name + '.pt'), torch.load(self.save_path + Y_name + '.pt')

    def getAnchors_fromMem(self, Anchor_name):
        return torch.load(self.save_path + Anchor_name + '.pt')

data_path = "NumPlateData/"

image_scale = 7
image_size = (image_scale*32, image_scale*32)
scaling_fact = 32

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

ExtractTrainData = DataExtractor (
                                data_path=data_path + 'train/', 
                                save_path=data_path,
                                annotations_csv="_annotations.csv", 
                                scaled_image_size=image_size, 
                                anchor_nos=5,
                                scaling_fact=scaling_fact,
                                device=device
                            )

# ExtractTrainData.extractAnchors_toMem()
# ExtractTrainData.extractXY_toMem('X_Train', 'Y_Train', 'Anchor_train', print_interval = 1)