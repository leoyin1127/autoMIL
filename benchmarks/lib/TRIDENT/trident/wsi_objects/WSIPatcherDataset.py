from torch.utils.data import Dataset


class WSIPatcherDataset(Dataset):
    """ Dataset from a WSI patcher to directly read tiles on a slide  """
    
    def __init__(self, patcher, transform):
        self.patcher = patcher
        self.transform = transform
                              
    def __len__(self):
        return len(self.patcher)
    
    def __getitem__(self, index):
        tile, x, y = self.patcher[index]

        if self.transform:
            tile = self.transform(tile)

        return tile, (x, y)
